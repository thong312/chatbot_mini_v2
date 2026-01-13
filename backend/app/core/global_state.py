# app/core/global_state.py

from app.core.settings import settings
from app.services.embedding import LocalEmbedder
from app.services.rerank import LocalReranker
from app.services.milvus_store import ensure_collection, get_all_documents
from app.services.rag_pipeline import RAGPipeline

print("🚀 Đang khởi tạo Global RAG Pipeline...")

# 1. Khởi tạo các Model & DB
embedder = LocalEmbedder(settings.embed_model)
reranker = LocalReranker(settings.rerank_model)
collection = ensure_collection(dim=embedder.dim)

# 2. Load dữ liệu lần đầu (Nếu DB rỗng thì nó trả về [])
initial_docs = get_all_documents(collection)

# 3. Khởi tạo Pipeline TOÀN CỤC
# Biến này sẽ được import bởi cả query.py và documents.py
global_rag_pipeline = RAGPipeline(
    collection=collection, 
    embedder=embedder, 
    reranker=reranker, 
    all_docs_for_bm25=initial_docs
)