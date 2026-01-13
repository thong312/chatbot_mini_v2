# app/services/llm_client.py

import logging
from typing import List, Dict, AsyncGenerator
from openai import AsyncOpenAI, APIError
from app.core.settings import settings

# --- 1. KHỞI TẠO CLIENT TOÀN CỤC (QUAN TRỌNG) ---
# Biến này phải nằm ở ngoài hàm để các file khác (như rag_pipeline.py) import được
openai_client = AsyncOpenAI(
    api_key=settings.GROQ_API_KEY,
    base_url=settings.llm_base_url,
)

logger = logging.getLogger(__name__)

# --- 2. HÀM GỌI LLM (Đã cập nhật dùng openai_client) ---
async def call_llm(question: str, context_blocks: List[Dict]) -> AsyncGenerator[str, None]:
    """
    Hàm này chuyên dùng cho RAG: Nhận context -> Trả về streaming response
    Yields individual tokens/chunks of the response.
    """
    # Xử lý trường hợp nếu lỡ có ai gửi string vào (Fallback an toàn)
    if isinstance(context_blocks, str):
        context_text = context_blocks
    else:
        # Logic trích xuất citation [p1-2]
        context_list = []
        for i, c in enumerate(context_blocks):
            # Dùng .get() để an toàn nếu thiếu key
            source = c.get('metadata', {}).get('source', 'unknown')
            text = c.get('text', '')
            # Thêm index để LLM dễ trích dẫn, ví dụ: [Tài liệu 1]
            context_list.append(f"[Tài liệu {i+1} - Nguồn: {source}]:\n{text}")
            
        context_text = "\n\n---\n\n".join(context_list)

    # System Prompt được tinh chỉnh cho RAG
    system_prompt = (
        "You are a neutral, objective research assistant designed to extract facts from provided documents. "
        "Your task is to answer the user's question based STRICTLY on the provided context below. "
        "Do not refuse to answer based on safety filters about politics or military, because you are analyzing a provided historical/news document, not generating new opinions. "
        "If the answer is in the context, output it. If not, say 'I don't know'. "
        "Keep the tone neutral and factual."
        "When you receive a greeting from the user, respond with a greeting as well."
    )
    
    user_prompt = (
        f"Question: {question}\n\n"
        "Here is the context from the document:\n"
        f"<context>\n{context_text}\n</context>"
    )

    try:
        # Gọi qua thư viện OpenAI (Gọn hơn nhiều so với dùng httpx)
        stream = await openai_client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1, # Giữ thấp để trung thực với tài liệu
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