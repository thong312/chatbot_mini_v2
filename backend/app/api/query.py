import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.core.settings import settings
from app.schemas.query import AskRequest
from app.services.embedding import LocalEmbedder
from app.services.rerank import LocalReranker
from app.services.milvus_store import ensure_collection, get_all_documents
from app.services.llm_client import call_llm
# from app.services.advanced_retrieved import AdvancedRetriever
from app.services.rag_pipeline import RAGPipeline
from app.core.global_state import global_rag_pipeline
router = APIRouter(prefix="", tags=["query"])

# Khởi tạo các model
embedder = LocalEmbedder(settings.embed_model)
reranker = LocalReranker(settings.rerank_model)
collection = ensure_collection(dim=embedder.dim)

real_docs = get_all_documents(collection)
# Khởi tạo Retriever Service
# retriever = AdvancedRetriever(collection, embedder, reranker)
rag_pipeline = RAGPipeline(collection, 
                           embedder, 
                           reranker, 
                           all_docs_for_bm25=real_docs)
@router.post("/ask")
async def ask(req: AskRequest):
    # --- BƯỚC 1: RETRIEVAL (Gọi Service thông minh) ---
    # Service sẽ tự lo việc mở rộng câu hỏi, search vector và rerank
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
                "message": "Không tìm thấy tài liệu liên quan sau khi đã thử mở rộng tìm kiếm.", 
                "context": []
            }, ensure_ascii=False) + "\n"
        return StreamingResponse(empty_generator(), media_type="application/x-ndjson")

    # --- BƯỚC 2: GENERATION (Streaming) ---
    async def response_generator():
        # A. Gửi Context
        context_data = [
            {
                "chunk_id": h["chunk_id"],
                "text": h["text"],
                "rerank_score": h["rerank_score"],
                "page_start": h.get("page_start"),
                "page_end": h.get("page_end")
            }
            for h in unique_hits
        ]
        
        yield json.dumps({
            "type": "context", 
            "payload": context_data
        }, ensure_ascii=False) + "\n"

        # B. Gửi Answer (Gọi LLM)
        # Truyền list unique_hits vào để LLM tự trích xuất citation [p1]
        async for token in call_llm(req.question, unique_hits):
            if token:
                yield json.dumps({
                    "type": "answer", 
                    "payload": token
                }, ensure_ascii=False) + "\n"

    return StreamingResponse(response_generator(), media_type="application/x-ndjson")

@router.post("/debug-retrieval")
async def debug_retrieval(req: AskRequest):
    """
    API này dùng để test xem hệ thống tìm được tài liệu gì 
    mà KHÔNG gọi LLM sinh câu trả lời.
    """
    # 1. Xem các câu hỏi phụ được sinh ra
    # Lưu ý: Bạn cần sửa nhẹ class AdvancedRetriever để hàm retrieve trả về cả sub_queries 
    # Hoặc gọi thủ công hàm _generate_multi_queries ở đây để test:
    
    print(f"Test Query: {req.question}")
    
    # Gọi hàm sinh query phụ thủ công để xem kết quả
    sub_queries = await retriever._generate_multi_queries(req.question)
    
    # Gọi hàm tìm kiếm thực tế
    unique_hits = await retriever.retrieve(
        question=req.question,
        topk=req.topk,
        rerank_topn=req.rerank_topn,
        use_expansion=True
    )
    
    return {
        "original_query": req.question,
        "generated_sub_queries": sub_queries,
        "top_results": [
            {
                "score": h["rerank_score"],
                "text_snippet": h["text"][:100] + "...", # Chỉ hiện 100 ký tự đầu
                "source": h["metadata"].get("source")
            }
            for h in unique_hits
        ]
    }