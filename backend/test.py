from app.services.neo4j_store import search, get_driver
from app.services.embedding import LocalEmbedder
from app.core.settings import settings

# 1. Giả lập câu hỏi
question = "Thỏa thuận ngừng bắn giữa Campuchia và Thái Lan có hiệu lực khi nào?"

# 2. Tạo vector
embedder = LocalEmbedder(settings.embed_model)
q_vec = embedder.encode([question])[0].tolist()

# 3. Tìm trong Neo4j
print(f"🔎 Đang tìm: {question}")
results = search(q_vec, topk=3)

# 4. In kết quả
for res in results:
    print("-" * 50)
    print(f"ID: {res['chunk_id']} | Score: {res['score']:.4f} | Level: {res['level']}")
    print(f"Text: {res['text'][:150]}...")
    if res['parent_id']:
        print(f"👉 Có Parent ID: {res['parent_id']} (GraphRAG sẵn sàng!)")