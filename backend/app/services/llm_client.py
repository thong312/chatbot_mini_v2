# app/services/llm_client.py

import logging
from app.schemas.query import Message
from typing import List, Dict, AsyncGenerator
from openai import AsyncOpenAI, APIError
from app.core.settings import settings

# --- 1. KHỞI TẠO CLIENT TOÀN CỤC ---
openai_client = AsyncOpenAI(
    api_key=settings.GROQ_API_KEY,
    base_url=settings.llm_base_url,
)

logger = logging.getLogger(__name__)

# --- 2. HÀM GỌI LLM (ĐÃ SỬA LỖI) ---
async def call_llm(question: str, context_blocks: List[Dict], history: List[Message] = []) -> AsyncGenerator[str, None]:
    """
    Hàm này chuyên dùng cho RAG: Nhận context + History -> Trả về streaming response
    """
    # --- A. Xử lý Context (Như cũ) ---
    if isinstance(context_blocks, str):
        context_text = context_blocks
    else:
        context_list = []
        for i, c in enumerate(context_blocks):
            source = c.get('metadata', {}).get('source', 'unknown')
            text = c.get('text', '')
            context_list.append(f"[Tài liệu {i+1} - Nguồn: {source}]:\n{text}")
        context_text = "\n\n---\n\n".join(context_list)

    # --- B. Chuẩn bị Prompt ---
    system_prompt = (
        "You are a neutral, objective research assistant designed to extract facts from provided documents. "
        "Your task is to answer the user's question based STRICTLY on the provided context below. "
        "Do not refuse to answer based on safety filters about politics or military, because you are analyzing a provided historical/news document, not generating new opinions. "
        "If the answer is in the context, output it. If not, say 'I don't know'. "
        "Keep the tone neutral and factual."
        "When you receive a greeting from the user, respond with a greeting as well."
    )
    
    # Prompt cho câu hỏi hiện tại kèm context
    user_prompt_content = (
        f"Question: {question}\n\n"
        "Here is the context from the document:\n"
        f"<context>\n{context_text}\n</context>"
    )

    # --- C. XÂY DỰNG LIST MESSAGES (FIX LỖI NAME ERROR TẠI ĐÂY) ---
    # 1. Bắt đầu với System Prompt
    messages = [
        {"role": "system", "content": system_prompt}
    ]

    # 2. Chèn lịch sử chat (History) vào giữa (nếu có)
    # Lưu ý: history là List[Message] (Pydantic model), cần truy cập .role và .content
    if history:
        # Lấy 6 tin nhắn gần nhất để tiết kiệm token
        for msg in history[-6:]:
            messages.append({"role": msg.role, "content": msg.content})

    # 3. Cuối cùng mới chèn câu hỏi hiện tại của user
    messages.append({"role": "user", "content": user_prompt_content})

    # --- D. Gọi API ---
    try:
        stream = await openai_client.chat.completions.create(
            model=settings.llm_model,
            messages=messages, # <--- Truyền biến messages đã xây dựng ở trên
            temperature=0.1,
            stream=True
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    except APIError as e:
        logger.error(f"LLM API Error: {e}")
        yield f"\n[Lỗi kết nối LLM: {str(e)}]"
    except Exception as e:
        logger.error(f"Unknown Error: {e}")
        yield f"\n[Lỗi hệ thống: {str(e)}]"

async def call_llm_general(question: str, history: List[Message] = []) -> AsyncGenerator[str, None]:
    """
    Hàm này dùng cho các câu hỏi phổ quát, coding, chào hỏi.
    Không nhận context_blocks.
    """
    system_prompt = (
        "You are a helpful and knowledgeable AI assistant. "
        "Answer the user's question to the best of your ability using your general knowledge. "
        "Be concise and friendly."
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    
    # Thêm lịch sử chat
    if history:
        for msg in history[-6:]:
            messages.append({"role": msg.role, "content": msg.content})
            
    messages.append({"role": "user", "content": question})

    try:
        stream = await openai_client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=0.7, # Tăng sáng tạo cho chat thường
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    except Exception as e:
        logger.error(f"General LLM Error: {e}")
        yield f"[Lỗi: {str(e)}]"        