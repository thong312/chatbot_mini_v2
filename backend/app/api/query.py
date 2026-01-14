import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.schemas.query import AskRequest, Message
# Import Pipeline toàn cục (để dùng chung RAM với bên upload)
from app.core.global_state import global_rag_pipeline
from app.services.llm_client import call_llm
# Import service Chat History (MongoDB)
from app.services.chat_history import get_chat_history, add_message_to_history
import uuid
router = APIRouter(prefix="", tags=["query"])

# --- LƯU Ý: ĐÃ XÓA ĐOẠN KHỞI TẠO LOCAL MODEL ĐỂ TIẾT KIỆM RAM ---
# Chúng ta dùng global_rag_pipeline được import ở trên.

@router.post("/ask")
async def ask(req: AskRequest):
    """
    API trả lời câu hỏi:
    1. Lấy lịch sử từ MongoDB dựa trên session_id
    2. Retrieval (RAG)
    3. Generation (LLM) + Streaming
    4. Lưu lại hội thoại mới vào MongoDB
    """
    session_id = req.session_id if req.session_id else str(uuid.uuid4())
    # --- BƯỚC 1: CHUẨN BỊ DỮ LIỆU (Lấy History từ DB) ---
    # Thay vì tin vào req.history (client gửi), ta lấy từ Database cho chuẩn
    db_history_dicts = await get_chat_history(session_id)

    # Convert từ dict của Mongo sang object Message để call_llm hiểu
    # (Nếu db trả về rỗng thì list này rỗng, không sao cả)
    history_objs = [Message(**msg) for msg in db_history_dicts]

    # --- BƯỚC 2: RETRIEVAL (Search & Rerank) ---
    unique_hits = await global_rag_pipeline.run(
        original_question=req.question,
        topk=req.topk,
        rerank_topn=req.rerank_topn
    )

    # Nếu không tìm thấy gì
    if not unique_hits:
        async def empty_generator():
            yield json.dumps({
                "type": "error", 
                "message": "Không tìm thấy tài liệu liên quan.", 
                "context": []
            }, ensure_ascii=False) + "\n"
        return StreamingResponse(empty_generator(), media_type="application/x-ndjson")

    # --- BƯỚC 3: GENERATION & SAVING (Streaming) ---
    async def response_generator():
        # A. Lưu ngay câu hỏi của User vào DB (Để chắc chắn đã ghi nhận)
        await add_message_to_history(session_id, "user", req.question)

        # B. Gửi Context cho Client
        context_data = [
            {
                "chunk_id": h["chunk_id"],
                "text": h["text"],
                "rerank_score": h.get("rerank_score", 0),
                "source": h.get("metadata", {}).get("source", "unknown"),
                "page_start": h.get("metadata", {}).get("page_start"),
                "page_end": h.get("metadata", {}).get("page_end")
            }
            for h in unique_hits
        ]
        
        yield json.dumps({
            "type": "context", 
            "payload": context_data
        }, ensure_ascii=False) + "\n"

        # C. Gọi LLM và gom câu trả lời để lưu DB
        full_answer = ""
        
        # QUAN TRỌNG: Truyền history_objs (lấy từ DB) vào đây
        async for token in call_llm(req.question, unique_hits, history_objs):
            if token:
                full_answer += token
                yield json.dumps({
                    "type": "answer", 
                    "payload": token
                }, ensure_ascii=False) + "\n"
        
        # D. Lưu câu trả lời trọn vẹn của Bot vào DB
        if full_answer:
            await add_message_to_history(session_id, "assistant", full_answer)

    return StreamingResponse(response_generator(), media_type="application/x-ndjson")

@router.post("/debug-retrieval")
async def debug_retrieval(req: AskRequest):
    """
    API debug xem Pipeline đang tìm kiếm như thế nào (không gọi LLM)
    """
    print(f"🛠️ Debug Query: {req.question}")
    
    # 1. Test sinh Query phụ (Query Expansion)
    # Lưu ý: Hàm _query_processing là private, chỉ dùng để debug
    sub_queries = await global_rag_pipeline._query_processing(req.question)
    
    # 2. Chạy tìm kiếm thật
    unique_hits = await global_rag_pipeline.run(
        original_question=req.question,
        topk=req.topk,
        rerank_topn=req.rerank_topn
    )
    
    return {
        "original_query": req.question,
        "generated_sub_queries": sub_queries,
        "results_count": len(unique_hits),
        "top_results": [
            {
                "score": h.get("rerank_score", 0),
                "text_snippet": h["text"][:150] + "...", # Cắt ngắn cho dễ nhìn
                "source_method": h.get("metadata", {}).get("source_method", "unknown")
            }
            for h in unique_hits
        ]
    }