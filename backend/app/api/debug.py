# app/api/debug.py
from typing import Literal
from fastapi import APIRouter, Query, UploadFile, File
from app.services.chucking.token_chunker import chunk_by_tokens_per_page
from app.services.chucking.sentence_chunker import chunk_by_sentences
# Đảm bảo tên file khớp với nơi bạn lưu hàm chunk_hierarchical mới
from app.services.chucking.hierarchical_chunker import chunk_hierarchical
from app.services.pdf_ingest import sha256_bytes, extract_pages
from app.core.settings import settings

router = APIRouter()

@router.post("/debug/chunking")
async def debug_chunking(
    file: UploadFile = File(...),
    strategy: str = Query("sentence", enum=["token", "sentence", "hierarchical"]),
    
    # --- Common params ---
    chunk_size: int = Query(500, ge=100, le=2000, description="Kích thước chunk con (hoặc chunk thường)"),
    
    # --- Token/Sentence params ---
    overlap: int = Query(80, ge=0, le=500, description="Overlap cho chiến lược Token"),
    overlap_sentences: int = Query(2, ge=0, le=10, description="Số câu gối đầu cho Sentence/Hierarchical"),
    
    # --- Hierarchical specific ---
    coarse_target_tokens: int = Query(1024, ge=500, le=4000, description="Kích thước Parent Chunk"),
    coarse_overlap_tokens: int = Query(200, ge=0, le=1000, description="Độ gối đầu của Parent Chunk (quan trọng)"),
    return_level: Literal["fine", "coarse", "both"] = Query("fine"),
):
    # 1) Read file bytes
    pdf_bytes = await file.read()
    doc_id = sha256_bytes(pdf_bytes)

    # 2) Extract pages
    pages = extract_pages(pdf_bytes)

    # 3) Chunking theo strategy
    if strategy == "token":
        chunks = chunk_by_tokens_per_page(
            pages=pages,
            tokenizer_model=settings.embed_model,
            chunk_size=chunk_size,
            overlap=overlap,
        )
    elif strategy == "sentence":
        chunks = chunk_by_sentences(
            pages=pages,
            tokenizer_model=settings.embed_model,
            chunk_size=chunk_size,
            overlap_sentences=overlap_sentences,
        )
    else: # hierarchical
        chunks = chunk_hierarchical(
            pages=pages,
            tokenizer_model=settings.embed_model,
            coarse_target_tokens=coarse_target_tokens,
            coarse_overlap_tokens=coarse_overlap_tokens, # <--- Bổ sung tham số này
            chunk_size=chunk_size,                       # Kích thước Child chunk
            overlap_sentences=overlap_sentences,         # Overlap của Child chunk
            return_level=return_level,
        )

    # 4) Trả preview
    return {
        "doc_id": doc_id,
        "filename": file.filename,
        "strategy": strategy,
        "params": {
            "chunk_size": chunk_size,
            "coarse_overlap": coarse_overlap_tokens if strategy == "hierarchical" else None,
            "level": return_level if strategy == "hierarchical" else None
        },
        "num_pages": len(pages),
        "num_chunks": len(chunks),
        # Preview 2 trang đầu để check text gốc
        "pages_sample": [
            {"page": p["page"], "len": len(p["text"]), "head": p["text"][:100] + "..."}
            for p in pages[:2]
        ],
        "chunks": [
            {
                "chunk_id": c["chunk_id"],
                "level": c.get("level", "standard"),
                "parent_id": c.get("parent_id"),
                "page_start": c["page_start"],
                "page_end": c["page_end"],
                "token_len": c.get("token_len"),
                # Chỉ hiện sentence_count nếu có (coarse chunk có thể không có key này tùy logic cũ/mới)
                "sentence_count": c.get("sentence_count"), 
                "head": c["text"][:100].replace("\n", " "),
                "tail": c["text"][-100:].replace("\n", " "),
                # Preview dài hơn chút để đọc
                "preview_full": c["text"][:300] + "..." if len(c["text"]) > 300 else c["text"]
            }
            for c in chunks
        ],
    }