from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
from app.core.settings import settings

def connect():
    connections.connect(alias="default", host=settings.milvus_host, port=str(settings.milvus_port))

def ensure_collection(dim: int) -> Collection:
    connect()
    name = settings.milvus_collection

    # --- QUAN TRỌNG: NẾU MUỐN RESET DB THÌ BỎ COMMENT DÒNG DƯỚI ---
    # utility.drop_collection(name) 
    
    if utility.has_collection(name):
        col = Collection(name)
        col.load()
        return col

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=128),
        
        # --- THÊM 2 TRƯỜNG MỚI CHO HIERARCHICAL ---
        FieldSchema(name="level", dtype=DataType.VARCHAR, max_length=50),       # "fine" / "coarse"
        FieldSchema(name="parent_id", dtype=DataType.VARCHAR, max_length=128),  # ID của chunk cha (nếu có)
        # ------------------------------------------

        FieldSchema(name="page_start", dtype=DataType.INT32),
        FieldSchema(name="page_end", dtype=DataType.INT32),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
    ]
    schema = CollectionSchema(fields, description="PDF chunks for RAG")
    col = Collection(name, schema)

    col.create_index(
        field_name="embedding",
        index_params={
            "index_type": "HNSW",
            "metric_type": "IP",
            "params": {"M": 16, "efConstruction": 200},
        },
    )
    col.load()
    return col

def insert_chunks(col: Collection, rows: list[dict]):
    # Cần đảm bảo thứ tự fields khớp với Schema ở trên
    entities = [
        [r["document_id"] for r in rows],
        [r["chunk_id"] for r in rows],
        
        # --- INSERT DATA CHO 2 TRƯỜNG MỚI ---
        # Dùng .get() để tránh lỗi nếu chunk cũ không có key này
        [r.get("level", "standard") for r in rows], 
        [r.get("parent_id") or "" for r in rows], # Lưu ý: Milvus chuỗi thì nên để "" thay vì None
        # ------------------------------------

        [r["page_start"] for r in rows],
        [r["page_end"] for r in rows],
        [r["text"] for r in rows],
        [r["embedding"] for r in rows],
    ]
    col.insert(entities)
    col.flush()

def search(col: Collection, query_vec: list[float], topk: int = 30) -> list[dict]:
    res = col.search(
        data=[query_vec],
        anns_field="embedding",
        param={"metric_type": "IP", "params": {"ef": 64}},
        limit=topk,
        # --- LẤY THÊM LEVEL VÀ PARENT_ID KHI SEARCH ---
        output_fields=["document_id", "chunk_id", "level", "parent_id", "page_start", "page_end", "text"],
    )

    hits = []
    for h in res[0]:
        entity = h.entity
        hits.append({
            "score": float(h.score),
            "document_id": entity.get("document_id"),
            "chunk_id": entity.get("chunk_id"),
            
            # Map trường mới ra kết quả
            "level": entity.get("level"),
            "parent_id": entity.get("parent_id"),
            
            "page_start": int(entity.get("page_start")),
            "page_end": int(entity.get("page_end")),
            "text": entity.get("text"),
        })
    return hits

# --- HÀM MỚI: DÙNG ĐỂ LẤY TEXT CỦA PARENT ---
def get_chunk_by_id(col: Collection, chunk_id: str):
    """
    Truy vấn trực tiếp chunk theo ID (Dùng cho Hierarchical Retrieval)
    """
    if not chunk_id:
        return None
        
    res = col.query(
        expr=f'chunk_id == "{chunk_id}"',
        output_fields=["text", "page_start", "page_end", "chunk_id", "level"],
        limit=1
    )
    
    if res:
        return res[0] # Trả về dict chứa text
    return None

# Thêm vào cuối file app/services/milvus_store.py

def get_all_documents(col: Collection):
    """
    Hàm này lấy TOÀN BỘ dữ liệu để nạp cho BM25.
    Đồng thời gom các trường lẻ (level, page...) vào dict 'metadata' để khớp với logic Pipeline.
    """
    try:
        col.load()
        
        # Query lấy tất cả record có chunk_id khác rỗng
        # Lưu ý: Milvus giới hạn mặc định 16384 dòng. Nếu nhiều hơn phải dùng iterator.
        results = col.query(
            expr="chunk_id != ''", 
            output_fields=["chunk_id", "text", "document_id", "level", "parent_id", "page_start", "page_end"],
            limit=10000 
        )
        
        # CHUYỂN ĐỔI CẤU TRÚC (QUAN TRỌNG)
        # Schema của bạn là các trường lẻ, nhưng Pipeline lại cần 'metadata'
        # Ta sẽ tự tạo 'metadata' giả lập ở đây.
        formatted_docs = []
        for r in results:
            formatted_docs.append({
                "chunk_id": r["chunk_id"],
                "text": r["text"],
                "metadata": {
                    "document_id": r["document_id"],
                    "level": r.get("level", "standard"),
                    "parent_id": r.get("parent_id", ""),
                    "page_start": r["page_start"],
                    "page_end": r["page_end"]
                }
            })
            
        print(f"📚 Đã load {len(formatted_docs)} documents cho BM25.")
        return formatted_docs

    except Exception as e:
        print(f"⚠️ Lỗi khi load documents cho BM25: {e}")
        return []