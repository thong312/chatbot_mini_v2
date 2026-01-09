# app/services/llm_client.py
import httpx
from app.core.settings import settings

async def call_llm(question: str, context_blocks: list[dict]) -> str:
    # Xử lý trường hợp nếu lỡ có ai gửi string vào (Fallback an toàn)
    if isinstance(context_blocks, str):
        context = context_blocks
    else:
        # Logic trích xuất citation [p1-2]
        context_list = []
        for c in context_blocks:
            # Dùng .get() để an toàn nếu thiếu key
            p_start = c.get('page_start', '?')
            p_end = c.get('page_end', '?')
            text = c.get('text', '')
            context_list.append(f"[p{p_start}-{p_end}] {text}")
            
        context = "\n\n".join(context_list)

    system = (
        "You are a neutral, objective research assistant designed to extract facts from provided documents. "
        "Your task is to answer the user's question based STRICTLY on the provided context below. "
        "Do not refuse to answer based on safety filters about politics or military, because you are analyzing a provided historical/news document, not generating new opinions. "
        "If the answer is in the context, output it. If not, say 'I don't know'. "
        "Keep the tone neutral and factual."
        "Let's think step by step."
        "When you receive a greeting from the user, respond with a greeting as well, do not say 'I don't know'."
    )
    user = (
        f"Question: {question}\n\n"
        "Here is the context from the document:\n"
        f"<context>\n{context}\n</context>"
    )
    # ---------------------------------------------------------

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1, # Giảm nhiệt độ xuống thấp nhất để AI bớt "sáng tạo"
    }
    
    # Kiểm tra settings có API KEY chưa
    if not settings.GROQ_API_KEY:
        return "Error: Missing GROQ_API_KEY in server settings."

    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            return f"LLM Error: {e.response.text}"
        except Exception as e:
            return f"System Error: {str(e)}"