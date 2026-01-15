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
    - Trả về 'RAG': Nếu cần tra cứu tài liệu, thông tin cụ thể, hoặc ngữ cảnh đã có hoặc đã upload trước đó.
    - Trả về 'GENERAL': Nếu là chào hỏi, coding, kiến thức phổ quát (thủ đô nước Pháp, cách nấu phở...).
    """
    system_prompt = (
        "Bạn là 'Người gác cổng' (Gatekeeper) cho một hệ thống RAG (Retrieval-Augmented Generation). "
        "Nhiệm vụ DUY NHẤT của bạn là phân loại đầu vào của người dùng thành 'RAG' hoặc 'GENERAL'.\n\n"
        
        "*** CHỈ THỊ QUAN TRỌNG ***\n"
        "Giả định mặc định của bạn BẮT BUỘC phải là 'RAG'. Bạn chỉ được chọn 'GENERAL' trong các tình huống rất cụ thể, phi thực tế (non-factual).\n\n"

        "*** ĐỊNH NGHĨA DANH MỤC ***\n"
        "1. RAG (Tra cứu tài liệu) - Chọn cái này cho 95% các truy vấn, bao gồm:\n"
        "   - BẤT KỲ câu hỏi nào hỏi về sự kiện thực tế, tin tức, lịch sử, chính trị, luật pháp, hoặc định nghĩa.\n"
        "   - BẤT KỲ câu hỏi nào về các thực thể cụ thể (ví dụ: 'Maduro', 'Trump', 'Việt Nam', 'Chiến tranh', 'Công ty X'), ngay cả khi chúng nổi tiếng.\n"
        "   - BẤT KỲ câu hỏi nào dạng 'Ai', 'Cái gì', 'Ở đâu', 'Khi nào', 'Tại sao', 'Làm thế nào'.\n"
        "   - BẤT KỲ đề cập nào đến 'tài liệu', 'file', 'văn bản', 'tóm tắt', 'phân tích'.\n"
        "   - Các câu hỏi mơ hồ (ví dụ: 'Điều đó có thật không?', 'Giải thích cái này').\n\n"
        
        "2. GENERAL (Trò chuyện/Tác vụ) - Chọn cái này CHỈ KHI:\n"
        "   - Các câu chào hỏi/tạm biệt thuần túy (ví dụ: 'Xin chào', 'Hi', 'Chào buổi sáng', 'Tạm biệt', 'Cảm ơn').\n"
        "   - Yêu cầu viết code (ví dụ: 'Viết script Python', 'Sửa lỗi code này').\n"
        "   - Các tác vụ viết sáng tạo KHÔNG dựa trên sự thật (ví dụ: 'Làm thơ tình', 'Kể chuyện cười').\n"
        "   - Yêu cầu dịch thuật chung chung không có ngữ cảnh cụ thể.\n\n"

        "*** CÁC VÍ DỤ GÂY NHIỄU (KHÔNG ĐƯỢC SAI CÁC CÂU NÀY) ***\n"
        "User: 'Chiến tranh ở Thái Lan?' -> RAG (Đây là truy vấn sự kiện thực tế)\n"
        "User: 'Nicolas Maduro là ai?' -> RAG (Dù bạn biết ông ấy, người dùng muốn thông tin từ tài liệu)\n"
        "User: '1 + 1 bằng mấy?' -> GENERAL\n"
        "User: 'Viết code Java' -> GENERAL\n"
        "User: 'Tóm tắt giúp tôi' -> RAG\n"
        "User: 'Ông ấy có vợ không?' -> RAG (Truy vấn dựa trên ngữ cảnh)\n\n"

        "Trả lời chính xác duy nhất một từ: 'RAG' hoặc 'GENERAL'."
        )

    try:
        response = await router_client.chat.completions.create(
            model=settings.llm_agent_model, 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0.7, # Cần độ chính xác tuyệt đối
            max_tokens=10
        )
        decision = response.choices[0].message.content.strip().upper()
        
        # Fallback nếu LLM trả lời linh tinh
        if "RAG" in decision: return "RAG"
        return "GENERAL"

    except Exception as e:
        logger.error(f"Router Error: {e}")
        return "RAG" # Mặc định an toàn là tìm trong tài liệu