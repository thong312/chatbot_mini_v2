# app/services/milvus_store.py
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
from app.core.settings import settings

def connect():
    """Thiết lập kết nối đến Milvus"""
    try:
        connections.connect(alias="default", host=settings.milvus_host, port=str(settings.milvus_port))
        print(f"✅ Đã kết nối Milvus tại {settings.milvus_host}:{settings.milvus_port}")
    except Exception as e:
        print(f"❌ Lỗi kết nối Milvus: {e}")

def ensure_collection(dim: int) -> Collection:
    """
    Tạo hoặc load Collection.
    QUAN TRỌNG: Schema phải có trường 'metadata' để lưu tên file.
    """
    connect()
    name = settings.milvus_collection

    # --- [LƯU Ý] NẾU MUỐN RESET DB THÌ BỎ COMMENT DÒNG DƯỚI RỒI CHẠY LẠI 1 LẦN ---
    # utility.drop_collection(name) 
    
    if utility.has_collection(name):
        col = Collection(name)
        col.load()
        return col

    print(f"⚡ Đang tạo Collection mới: {name}")

    fields = [
        # Các trường cơ bản
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=128),
        
        # Các trường Hierarchical (Cha/Con)
        FieldSchema(name="level", dtype=DataType.VARCHAR, max_length=50),       # "fine" / "coarse"
        FieldSchema(name="parent_id", dtype=DataType.VARCHAR, max_length=128),  # ID chunk cha
        
        # Nội dung & Vector
        FieldSchema(name="page_start", dtype=DataType.INT32),
        FieldSchema(name="page_end", dtype=DataType.INT32),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),

        # --- [QUAN TRỌNG] TRƯỜNG METADATA (Lưu tên file, tiêu đề...) ---
        FieldSchema(name="metadata", dtype=DataType.JSON)
    ]

    schema = CollectionSchema(fields, description="PDF chunks for RAG with Metadata")
    col = Collection(name, schema)

    # Tạo Index cho Vector để tìm kiếm nhanh
    col.create_index(
        field_name="embedding",
        index_params={
            "index_type": "HNSW",
            "metric_type": "IP", # Inner Product (Cosine Similarity)
            "params": {"M": 16, "efConstruction": 200},
        },
    )
    col.load()
    return col

def insert_chunks(col: Collection, rows: list[dict]):
    """
    Chèn dữ liệu vào Milvus.
    Phải đảm bảo thứ tự các cột khớp 100% với Schema ở trên.
    """
    if not rows:
        return

    # Chuẩn bị dữ liệu theo cột (Columnar format)
    entities = [
        [r["document_id"] for r in rows],
        [r["chunk_id"] for r in rows],
        
        # Hierarchical fields
        [r.get("level", "standard") for r in rows], 
        [r.get("parent_id") or "" for r in rows],

        # Content fields
        [r["page_start"] for r in rows],
        [r["page_end"] for r in rows],
        [r["text"] for r in rows],
        [r["embedding"] for r in rows],

        # --- [QUAN TRỌNG] Insert Metadata ---
        # Nếu không có metadata, gán dict rỗng {}
        [r.get("metadata", {}) for r in rows]
    ]
    
    col.insert(entities)
    col.flush()
    print(f"✅ Đã insert {len(rows)} chunks vào Milvus.")

def search(col: Collection, query_vec: list[float], topk: int = 30) -> list[dict]:
    """
    Tìm kiếm Vector.
    Phải lấy trường 'metadata' ra để Frontend biết tên file.
    """
    res = col.search(
        data=[query_vec],
        anns_field="embedding",
        param={"metric_type": "IP", "params": {"ef": 64}},
        limit=topk,
        # --- LẤY CÁC TRƯỜNG CẦN THIẾT (BAO GỒM METADATA) ---
        output_fields=["document_id", "chunk_id", "level", "parent_id", "page_start", "page_end", "text", "metadata"],
    )

    hits = []
    for h in res[0]:
        entity = h.entity
        hits.append({
            "score": float(h.score),
            "document_id": entity.get("document_id"),
            "chunk_id": entity.get("chunk_id"),
            "level": entity.get("level"),
            "parent_id": entity.get("parent_id"),
            "page_start": int(entity.get("page_start")),
            "page_end": int(entity.get("page_end")),
            "text": entity.get("text"),
            
            # --- TRẢ VỀ METADATA ---
            "metadata": entity.get("metadata", {})
        })
    return hits

def get_chunk_by_id(col: Collection, chunk_id: str):
    """
    Lấy nội dung chunk theo ID (Dùng để lấy nội dung chunk Cha)
    """
    if not chunk_id:
        return None
        
    res = col.query(
        expr=f'chunk_id == "{chunk_id}"',
        output_fields=["text", "page_start", "page_end", "chunk_id", "level", "metadata"],
        limit=1
    )
    
    if res:
        return res[0]
    return None

def get_all_documents(col: Collection):
    """
    Lấy toàn bộ dữ liệu để cập nhật BM25.
    """
    try:
        col.load()
        # Query toàn bộ (Giới hạn 16k dòng, nếu nhiều hơn cần phân trang)
        results = col.query(
            expr="chunk_id != ''", 
            output_fields=["chunk_id", "text", "document_id", "level", "parent_id", "page_start", "page_end", "metadata"],
            limit=16384 
        )
        
        print(f"📚 Đã load {len(results)} documents cho BM25.")
        return results

    except Exception as e:
        print(f"⚠️ Lỗi khi load documents cho BM25: {e}")
        return []