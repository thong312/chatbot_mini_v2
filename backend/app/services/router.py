# app/services/router.py
from openai import AsyncOpenAI
from app.core.settings import settings
import logging

# Dùng chung client hoặc tạo mới tùy bạn
router_client = AsyncOpenAI(
    api_key=settings.AGENT_API_KEY,
    base_url=settings.llm_agent_base_url,
)

logger = logging.getLogger(__name__)

async def route_query(question: str) -> str:
    """
    Phân loại câu hỏi:
    - Trả về 'RAG': Nếu cần tra cứu tài liệu, thông tin cụ thể, hoặc ngữ cảnh đã có.
    - Trả về 'GENERAL': Nếu là chào hỏi, coding, kiến thức phổ quát (thủ đô nước Pháp, cách nấu phở...).
    """
    system_prompt = (
            "You are the Gatekeeper for a RAG (Retrieval-Augmented Generation) system. "
            "Your SOLE job is to classify the user's input into 'RAG' or 'GENERAL'.\n\n"
            
            "*** CRITICAL DIRECTIVE ***\n"
            "Your default assumption MUST be 'RAG'. You should only choose 'GENERAL' in very specific, non-factual scenarios.\n\n"

            "*** CATEGORY DEFINITIONS ***\n"
            "1. RAG (Search Document) - Select this for 95% of queries, including:\n"
            "   - ANY question asking for facts, news, history, politics, laws, or definitions.\n"
            "   - ANY question about specific entities (e.g., 'Maduro', 'Trump', 'Vietnam', 'War', 'Company X'), even if they are famous.\n"
            "   - ANY question asking 'Who', 'What', 'Where', 'When', 'Why', 'How'.\n"
            "   - ANY mention of 'document', 'file', 'text', 'summary', 'analyze'.\n"
            "   - Ambiguous queries (e.g., 'Is it true?', 'Explain this').\n\n"
            
            "2. GENERAL (Chat/Task) - Select this ONLY for:\n"
            "   - Pure greetings/farewells (e.g., 'Hello', 'Hi', 'Good morning', 'Bye', 'Thank you').\n"
            "   - Requests to write code (e.g., 'Write a Python script', 'Fix this bug').\n"
            "   - Creative writing tasks NOT based on facts (e.g., 'Write a poem about love', 'Tell me a joke').\n"
            "   - General translation requests without context.\n\n"

            "*** ADVERSARIAL EXAMPLES (DO NOT FAIL THESE) ***\n"
            "User: 'Chiến tranh ở Thái Lan?' -> RAG (It's a factual event query)\n"
            "User: 'Nicolas Maduro là ai?' -> RAG (Even if you know him, the user wants the document's perspective)\n"
            "User: '1 + 1 bằng mấy?' -> GENERAL\n"
            "User: 'Viết code Java' -> GENERAL\n"
            "User: 'Tóm tắt giúp tôi' -> RAG\n"
            "User: 'Ông ấy có vợ không?' -> RAG (Contextual query)\n\n"

            "Reply with strictly one word: 'RAG' or 'GENERAL'."
        )

    try:
        response = await router_client.chat.completions.create(
            model=settings.llm_agent_model, 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0, # Cần độ chính xác tuyệt đối
            max_tokens=10
        )
        decision = response.choices[0].message.content.strip().upper()
        
        # Fallback nếu LLM trả lời linh tinh
        if "RAG" in decision: return "RAG"
        return "GENERAL"

    except Exception as e:
        logger.error(f"Router Error: {e}")
        return "RAG" # Mặc định an toàn là tìm trong tài liệu