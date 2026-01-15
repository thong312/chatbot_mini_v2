import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.schemas.query import AskRequest, Message
# Import Pipeline toàn cục (để dùng chung RAM với bên upload)
from app.core.global_state import global_rag_pipeline
from app.services.llm_client import call_llm, call_llm_general
# Import service Chat History (MongoDB)
from app.services.chat_history import get_chat_history, add_message_to_history
import uuid

from app.services.router import route_query


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

    initial_mode = await route_query(req.question)
    print(f"🎯 Router Initial: {initial_mode}")
    

    async def response_generator():
        final_mode = initial_mode
        unique_hits = []
        
        # --- BƯỚC QUAN TRỌNG: RAG FALLBACK LOGIC ---
        if initial_mode == "RAG":
            # A. Thử tìm kiếm trong Vector DB
            unique_hits = await global_rag_pipeline.run(
                original_question=req.question,
                topk=req.topk,
                rerank_topn=req.rerank_topn
            )

            # B. Kiểm tra chất lượng kết quả (Fallback)
            # Ngưỡng (Threshold): Với BGE-Reranker, điểm < -2 thường là không liên quan
            # Bạn có thể chỉnh số -2.0 này tùy theo thực tế (VD: -1.0, 0.0)
            SCORE_THRESHOLD = -2.0 
            
            is_bad_result = False
            
            if not unique_hits:
                print("⚠️ RAG rỗng: Không tìm thấy tài liệu nào.")
                is_bad_result = True
            elif unique_hits[0]['rerank_score'] < SCORE_THRESHOLD:
                print(f"⚠️ RAG kém: Điểm cao nhất chỉ là {unique_hits[0]['rerank_score']} (Dưới ngưỡng {SCORE_THRESHOLD})")
                is_bad_result = True
            
            # C. Nếu kết quả tệ -> Chuyển sang GENERAL
            if is_bad_result:
                final_mode = "GENERAL"
                unique_hits = [] # Xóa kết quả rác để không làm nhiễu LLM

        # 3. Gửi thông tin Mode về cho Client (để hiện màu Badge)
        yield json.dumps({
            "type": "meta_info", 
            "session_id": session_id,
            "mode": final_mode # Client sẽ hiển thị General (Tím) hoặc RAG (Xanh) dựa vào cái này
        }, ensure_ascii=False) + "\n"

        # 4. Lưu câu hỏi User
        await add_message_to_history(session_id, "user", req.question)

        full_answer = ""

        # --- NHÁNH XỬ LÝ ---
        
        # TRƯỜNG HỢP 1: RAG xịn (Có tài liệu ngon)
        if final_mode == "RAG" and unique_hits:
            # Gửi Context
            context_data = [
                {
                    "chunk_id": h["chunk_id"], "text": h["text"], 
                    "rerank_score": h.get("rerank_score", 0), "metadata": h.get("metadata")
                } for h in unique_hits
            ]
            yield json.dumps({"type": "context", "payload": context_data}, ensure_ascii=False) + "\n"
            
            # Gọi LLM trả lời dựa trên tài liệu
            async for token in call_llm(req.question, unique_hits, history_objs):
                if token:
                    full_answer += token
                    yield json.dumps({"type": "answer", "payload": token}, ensure_ascii=False) + "\n"

        # TRƯỜNG HỢP 2: GENERAL (Hoặc RAG bị Fail chuyển sang)
        else:
            # Có thể thêm một câu thông báo nhỏ nếu bị fallback
            if initial_mode == "RAG": 
                # Nếu ban đầu định tìm kiếm mà không thấy, báo nhẹ 1 câu (tùy chọn)
                msg = "*(Không tìm thấy thông tin trong tài liệu, tôi sẽ trả lời bằng kiến thức tổng quát...)*\n\n"
                full_answer += msg
                yield json.dumps({"type": "answer", "payload": msg}, ensure_ascii=False) + "\n"

            # Gọi LLM chém gió (Sử dụng kiến thức training của nó)
            async for token in call_llm_general(req.question, history_objs):
                if token:
                    full_answer += token
                    yield json.dumps({"type": "answer", "payload": token}, ensure_ascii=False) + "\n"

        # 5. Lưu câu trả lời
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