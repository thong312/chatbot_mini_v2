# app/services/llm_client.py
import httpx
from app.core.settings import settings

async def call_llm(question: str, context_blocks: list[dict]):
    """
    Async generator that streams tokens from the LLM.
    Yields individual tokens/chunks of the response.
    """
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
        "stream": True,  # Enable streaming
    }
    
    # Kiểm tra settings có API KEY chưa
    if not settings.GROQ_API_KEY:
        yield "Error: Missing GROQ_API_KEY in server settings."
        return

    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            async with client.stream(
                "POST",
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                if response.status_code >= 400:
                    yield f"LLM Error: {response.status_code}"
                    return
                
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    # Groq uses SSE format: "data: {...}"
                    if line.startswith("data: "):
                        line = line[6:]  # Remove "data: " prefix
                    
                    if line == "[DONE]":
                        break
                    
                    try:
                        import json
                        chunk = json.loads(line)
                        token = chunk["choices"][0]["delta"].get("content", "")
                        if token:
                            yield token
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                        
        except httpx.HTTPStatusError as e:
            yield f"LLM Error: {e.response.text}"
        except Exception as e:
            yield f"System Error: {str(e)}"