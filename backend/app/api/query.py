from fastapi import APIRouter
from app.core.settings import settings
from app.schemas.query import AskRequest, AskResponse
from app.services.embedding import LocalEmbedder
from app.services.rerank import LocalReranker
from app.services.milvus_store import ensure_collection, search
from app.services.llm_client import call_llm

router = APIRouter(prefix="", tags=["query"])

# Khởi tạo model 1 lần duy nhất khi start app
embedder = LocalEmbedder(settings.embed_model)
reranker = LocalReranker(settings.rerank_model)
collection = ensure_collection(dim=embedder.dim)

@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    # 1. Semantic Search (Vector)
    qvec = embedder.encode([req.question])[0]
    hits = search(collection, qvec, topk=req.topk)

    if not hits:
        return AskResponse(answer="Không tìm thấy tài liệu liên quan.", context=[])

    # 2. Rerank (Sắp xếp lại bằng model xịn hơn)
    passages = [h["text"] for h in hits]
    rr_scores = reranker.rerank(req.question, passages)

    for h, s in zip(hits, rr_scores):
        h["rerank_score"] = float(s)

    # Sắp xếp theo điểm rerank cao nhất
    hits_sorted = sorted(hits, key=lambda x: x["rerank_score"], reverse=True)

    # 3. Deduplication (Khử trùng lặp quan trọng)
    # Rất quan trọng với Hierarchical vì vector con thường cụm lại gần nhau
    seen_ids = set()
    unique_hits = []
    
    for h in hits_sorted:
        if h["chunk_id"] not in seen_ids:
            unique_hits.append(h)
            seen_ids.add(h["chunk_id"])
        
        # Chỉ lấy đủ số lượng rerank_topn yêu cầu
        if len(unique_hits) >= req.rerank_topn:
            break

    # 4. Context Construction (Tạo ngữ cảnh sạch)
    # Chỉ lấy phần TEXT để gửi cho LLM, loại bỏ metadata rác
    context_str = "\n\n---\n\n".join([h["text"] for h in unique_hits])

    # Debug: In ra terminal để xem context gửi đi có đúng không
    # print(f"Context sending to LLM ({len(context_str)} chars):\n{context_str[:200]}...")

    # 5. Gọi LLM
    answer = await call_llm(req.question, context_str)

    # 6. Trả về kết quả
    return AskResponse(
        answer=answer,
        context=[
            {
                "chunk_id": h["chunk_id"],
                "level": h.get("level", "unknown"), # Thêm info level để debug
                "parent_id": h.get("parent_id"),    # Thêm info parent
                "page_start": h.get("page_start"),
                "page_end": h.get("page_end"),
                "rerank_score": h["rerank_score"],
                "text": h["text"]
            }
            for h in unique_hits
        ],
    )