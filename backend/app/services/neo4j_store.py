# app/services/neo4j_store.py
from neo4j import GraphDatabase, Driver
from app.core.settings import settings
import json

class Neo4jClient:
    _driver: Driver = None

    @classmethod
    def get_driver(cls) -> Driver:
        if cls._driver is None:
            try:
                cls._driver = GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password)
                )
                print(f"✅ Đã kết nối Neo4j tại {settings.neo4j_uri}")
            except Exception as e:
                print(f"❌ Lỗi kết nối Neo4j: {e}")
                raise e
        return cls._driver

    @classmethod
    def close(cls):
        if cls._driver:
            cls._driver.close()
            cls._driver = None

def get_driver():
    return Neo4jClient.get_driver()

def ensure_vector_index(dim: int):
    """
    Tạo Vector Index cho node Chunk nếu chưa có.
    """
    driver = get_driver()
    index_name = "chunk_embedding_index"
    
    # Neo4j 5.x syntax for vector index
    query_create = f"""
    CREATE VECTOR INDEX {index_name} IF NOT EXISTS
    FOR (c:Chunk) ON (c.embedding)
    OPTIONS {{indexConfig: {{
      `vector.dimensions`: {dim},
      `vector.similarity_function`: 'cosine'
    }}}}
    """
    
    try:
        with driver.session(database=settings.neo4j_database) as session:
            # Create constraint for unique chunk_id
            session.run("CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE")
            
            # Create vector index
            print(f"⚡ Đang kiểm tra/tạo Vector Index: {index_name}")
            session.run(query_create)
            print(f"✅ Vector Index '{index_name}' đã sẵn sàng.")
    except Exception as e:
        print(f"❌ Lỗi tạo index Neo4j: {e}")
        
def insert_chunks(rows: list[dict]):
    """
    Chèn dữ liệu Chunk vào Neo4j.
    """
    if not rows:
        return

    driver = get_driver()
    
    # --- SỬA ĐOẠN QUERY NÀY ---
    query = """
    UNWIND $rows AS row
    MERGE (c:Chunk {chunk_id: row.chunk_id})
    SET c.document_id = row.document_id,
        c.text = row.text,
        c.page_start = row.page_start,
        c.page_end = row.page_end,
        c.level = row.level,
        c.parent_id = row.parent_id,
        c.embedding = row.embedding,
        c.metadata = row.metadata_json
    
    // --- SỬA LỖI Ở ĐÂY: Đổi '#' thành '//' ---
    // Create relationship to parent if exists
    WITH c, row
    WHERE row.parent_id IS NOT NULL AND row.parent_id <> ""
    MERGE (p:Chunk {chunk_id: row.parent_id})
    MERGE (c)-[:HAS_PARENT]->(p)
    """
    # --------------------------

    # Pre-process rows to serialize metadata if needed
    processed_rows = []
    for r in rows:
        row_copy = r.copy()
        # Xử lý metadata thành JSON string
        if "metadata" in row_copy and isinstance(row_copy["metadata"], dict):
             row_copy["metadata_json"] = json.dumps(row_copy["metadata"])
        else:
             row_copy["metadata_json"] = "{}"
        
        # Đảm bảo các trường này tồn tại để tránh lỗi thiếu key
        if "level" not in row_copy: row_copy["level"] = "standard"
        if "parent_id" not in row_copy: row_copy["parent_id"] = ""
        
        processed_rows.append(row_copy)

    with driver.session(database=settings.neo4j_database) as session:
        session.run(query, rows=processed_rows)
    
    print(f"✅ Đã insert/update {len(rows)} chunks vào Neo4j.")

def search(query_vec: list[float], topk: int = 30) -> list[dict]:
    """
    Tìm kiếm vector similarity trong Neo4j.
    """
    driver = get_driver()
    index_name = "chunk_embedding_index"
    
    # Neo4j 5.x vector search procedure
    query = f"""
    CALL db.index.vector.queryNodes($index_name, $topk, $embedding)
    YIELD node, score
    RETURN node.document_id as document_id,
           node.chunk_id as chunk_id,
           node.level as level,
           node.parent_id as parent_id,
           node.page_start as page_start,
           node.page_end as page_end,
           node.text as text,
           node.metadata as metadata_json,
           score
    """
    
    results = []
    with driver.session(database=settings.neo4j_database) as session:
        result = session.run(query, index_name=index_name, topk=topk, embedding=query_vec)
        for record in result:
            metadata = {}
            if record["metadata_json"]:
                try:
                    metadata = json.loads(record["metadata_json"])
                except:
                    pass
            
            results.append({
                "score": record["score"],
                "document_id": record["document_id"],
                "chunk_id": record["chunk_id"],
                "level": record["level"],
                "parent_id": record["parent_id"],
                "page_start": record["page_start"],
                "page_end": record["page_end"],
                "text": record["text"],
                "metadata": metadata
            })
            
    return results

def get_chunk_by_id(chunk_id: str):
    """
    Lấy nội dung chunk theo ID.
    """
    if not chunk_id:
        return None
        
    driver = get_driver()
    query = """
    MATCH (c:Chunk {chunk_id: $chunk_id})
    RETURN c.chunk_id as chunk_id,
           c.text as text,
           c.page_start as page_start,
           c.page_end as page_end,
           c.level as level,
           c.metadata as metadata_json
    """
    
    with driver.session(database=settings.neo4j_database) as session:
        result = session.run(query, chunk_id=chunk_id).single()
        if result:
            metadata = {}
            if result["metadata_json"]:
                try:
                    metadata = json.loads(result["metadata_json"])
                except:
                    pass
            return {
                "chunk_id": result["chunk_id"],
                "text": result["text"],
                "page_start": result["page_start"],
                "page_end": result["page_end"],
                "level": result["level"],
                "metadata": metadata
            }
    return None

def get_all_documents(limit: int = 16384):
    """
    Lấy toàn bộ documents (chunks) để build BM25.
    """
    driver = get_driver()
    query = """
    MATCH (c:Chunk)
    RETURN c.chunk_id as chunk_id,
           c.text as text,
           c.document_id as document_id,
           c.level as level,
           c.parent_id as parent_id,
           c.page_start as page_start,
           c.page_end as page_end,
           c.metadata as metadata_json
    LIMIT $limit
    """
    
    docs = []
    try:
        with driver.session(database=settings.neo4j_database) as session:
            result = session.run(query, limit=limit)
            for record in result:
                metadata = {}
                if record["metadata_json"]:
                    try:
                        metadata = json.loads(record["metadata_json"])
                    except:
                        pass
                docs.append({
                    "chunk_id": record["chunk_id"],
                    "text": record["text"],
                    "document_id": record["document_id"],
                    "level": record["level"],
                    "parent_id": record["parent_id"],
                    "page_start": record["page_start"],
                    "page_end": record["page_end"],
                    "metadata": metadata
                })
        print(f"📚 Đã load {len(docs)} documents từ Neo4j cho BM25.")
        return docs
    except Exception as e:
        print(f"⚠️ Lỗi khi load documents cho BM25: {e}")
        return []

def delete_all_chunks():
    """Xóa toàn bộ dữ liệu Chunk"""
    driver = get_driver()
    query = "MATCH (c:Chunk) DETACH DELETE c"
    with driver.session(database=settings.neo4j_database) as session:
        session.run(query)
    print("🗑️ Đã xóa toàn bộ Chunk trong Neo4j")
