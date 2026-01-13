from http.client import HTTPException
from typing import List
from fastapi import APIRouter, UploadFile, File
from app.core.settings import settings
from app.schemas.document import IngestResponse
from app.services.pdf_ingest import sha256_bytes, extract_pages
from app.services.chucking.hierarchical_chunker import chunk_hierarchical
from app.services.embedding import LocalEmbedder
from app.services.milvus_store import ensure_collection, insert_chunks
from app.services.minio_store import upload_pdf_to_minio, get_file_stream
from app.services.minio_store import list_files_in_minio
from fastapi.responses import StreamingResponse

from app.core.global_state import global_rag_pipeline, collection 
from app.services.milvus_store import get_all_documents

router = APIRouter(prefix="/documents", tags=["documents"])

# init once
embedder = LocalEmbedder(settings.embed_model)
collection = ensure_collection(dim=embedder.dim)

@router.post("/ingest", response_model=IngestResponse)
async def ingest_pdf(file: UploadFile = File(...)):
    pdf_bytes = await file.read()
    doc_hash = sha256_bytes(pdf_bytes)
    document_id = doc_hash[:12]

    try:
        minio_filename = f"{document_id}.pdf"
        upload_pdf_to_minio(
            file_bytes=pdf_bytes, 
            file_name=minio_filename
        )
        print(f"Đã lưu file gốc vào MinIO: {minio_filename}")
        
    except Exception as e:
        print(f"❌ Lỗi MinIO: {e}")

    pages = extract_pages(pdf_bytes)
    
    # 1. SỬA chunking call
    chunks = chunk_hierarchical(
            pages=pages,
            tokenizer_model=settings.embed_model,
            coarse_target_tokens=512, # Kích thước Parent
            coarse_overlap_tokens=200, # Overlap Parent
            chunk_size=128,            # Kích thước Child
            overlap_sentences=2,
            
            # --- QUAN TRỌNG: PHẢI LÀ "BOTH" ---
            # Để lưu cả Cha (để đọc) và Con (để tìm kiếm) vào DB
            return_level="both", 
        )

    texts = [c["text"] for c in chunks]
    vecs = embedder.encode(texts)

    rows = []
    for c, v in zip(chunks, vecs):
        rows.append({
            "document_id": document_id,
            "chunk_id": c["chunk_id"],
            "page_start": c["page_start"],
            "page_end": c["page_end"],
            "text": c["text"],
            "embedding": v,
            
            # --- 2. BỔ SUNG MAP DỮ LIỆU MỚI ---
            # Lấy thông tin từ kết quả chunker để gửi vào DB
            "level": c.get("level", "standard"),      
            "parent_id": c.get("parent_id") or "",    # Nếu không có (là chunk cha) thì để rỗng
        })

    insert_chunks(collection, rows)
    print("⚡ Triggering BM25 Update...")
    current_docs = get_all_documents(collection)
    global_rag_pipeline.reload_bm25(current_docs)
    return IngestResponse(document_id=document_id, chunks_inserted=len(rows), filename=file.filename)

@router.get("", response_model=List[dict])
async def get_documents():
    """
    API lấy danh sách file từ MinIO để hiển thị lên Sidebar
    """
    return list_files_in_minio()

@router.get("/view/{filename}")
def view_document(filename: str):
    """
    Stream nội dung file PDF về trình duyệt để xem trước (Preview)
    """
    file_stream = get_file_stream(filename)

    if not file_stream:
        raise HTTPException(status_code=404, detail="Không tìm thấy file trong MinIO")

    # Trả về dạng StreamingResponse
    # media_type="application/pdf": Báo cho trình duyệt biết đây là PDF
    # content-disposition="inline": Báo trình duyệt MỞ FILE thay vì TẢI VỀ
    return StreamingResponse(
        content=file_stream,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )