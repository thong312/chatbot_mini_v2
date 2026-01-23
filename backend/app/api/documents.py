from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.core.settings import settings
from app.schemas.document import IngestResponse
from app.services.pdf_ingest import sha256_bytes, extract_pages
from app.services.chucking.hierarchical_chunker import chunk_hierarchical
from app.services.embedding import LocalEmbedder
from app.services.neo4j_store import ensure_vector_index, insert_chunks, get_all_documents
from app.services.minio_store import upload_pdf_to_minio, get_file_stream
from app.services.minio_store import list_files_in_minio
from fastapi.responses import StreamingResponse

from app.core.global_state import global_rag_pipeline

router = APIRouter(prefix="/documents", tags=["documents"])

# init once
embedder = LocalEmbedder(settings.embed_model)
# Ensure vector index exists in Neo4j
ensure_vector_index(dim=embedder.dim)

@router.post("/ingest", response_model=IngestResponse)
async def ingest_pdf(file: UploadFile = File(...)):
    pdf_bytes = await file.read()
    doc_hash = sha256_bytes(pdf_bytes)
    document_id = doc_hash[:12]

    # --- [SỬA 1] LƯU MINIO BẰNG TÊN FILE GỐC ---
    # Để khi Frontend gọi /view/ten_file.pdf thì MinIO mới tìm thấy.
    # (Code cũ dùng document_id.pdf khiến frontend bị lỗi 404 khi bấm xem)
    minio_filename = file.filename 

    try:
        upload_pdf_to_minio(
            file_bytes=pdf_bytes, 
            file_name=minio_filename
        )
        print(f"✅ Đã lưu file vào MinIO: {minio_filename}")
        
    except Exception as e:
        print(f"❌ Lỗi MinIO: {e}")

    # Xử lý Chunking
    pages = extract_pages(pdf_bytes)
    chunks = chunk_hierarchical(
        pages=pages,
        tokenizer_model=settings.embed_model,
        coarse_target_tokens=512,
        coarse_overlap_tokens=200,
        chunk_size=128,
        overlap_sentences=2,
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
            "level": c.get("level", "standard"),
            "parent_id": c.get("parent_id") or "",
            
            # --- [SỬA 2] THÊM METADATA ---
            # Đây là phần quan trọng để Frontend hiển thị được tên file
            "metadata": {
                "source": file.filename,  # <--- Tên file hiển thị
                "page": c["page_start"],  # Số trang
                "total_pages": len(pages)
            }
        })

    insert_chunks(rows)
    
    # Reload lại BM25 Search
    print("⚡ Triggering BM25 Update...")
    current_docs = get_all_documents()
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