import asyncio
from typing import List, Dict
from app.services.embedding import LocalEmbedder
from app.services.rerank import LocalReranker
from app.services.milvus_store import search
from app.core.settings import settings
# Import client LLM để dùng cho việc sinh câu hỏi phụ
from openai import AsyncOpenAI 

class AdvancedRetriever:
    def __init__(self, collection, embedder: LocalEmbedder, reranker: LocalReranker):
        self.collection = collection
        self.embedder = embedder
        self.reranker = reranker
        
        # Client riêng để gọi LLM nhanh cho việc sinh query (nhẹ)
        self.llm_client = AsyncOpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url=settings.llm_base_url,
        )

    async def _generate_multi_queries(self, question: str, n=3) -> List[str]:
        """
        Kỹ thuật Query Expansion: Dùng LLM sinh ra n biến thể của câu hỏi gốc
        để tìm kiếm bao quát hơn.
        """
        system_prompt = """Bạn là một chuyên gia tìm kiếm tin học. 
        Nhiệm vụ: Hãy tạo ra 3 câu hỏi tìm kiếm khác nhau dựa trên câu hỏi gốc của người dùng để tìm kiếm tài liệu kỹ thuật tốt hơn.
        Chỉ trả về các câu hỏi, mỗi câu một dòng. Không giải thích gì thêm."""
        
        try:
            response = await self.llm_client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0.7,
                max_tokens=150
            )
            content = response.choices[0].message.content.strip()
            # Tách các dòng thành list
            queries = [line.strip("- ").strip() for line in content.split("\n") if line.strip()]
            return queries[:n] # Chỉ lấy n câu
        except Exception as e:
            print(f"⚠️ Lỗi sinh query phụ: {e}")
            return []

    async def retrieve(self, question: str, topk: int = 5, rerank_topn: int = 3, use_expansion: bool = True):
        """
        Hàm tìm kiếm thông minh:
        1. (Option) Sinh query phụ.
        2. Vector Search cho TẤT CẢ query.
        3. Gộp kết quả & Khử trùng lặp.
        4. Rerank kết quả tổng hợp.
        """
        
        # 1. Chuẩn bị danh sách câu hỏi để tìm
        search_queries = [question]
        if use_expansion:
            print(f"🔍 Đang mở rộng câu hỏi: '{question}'...")
            sub_queries = await self._generate_multi_queries(question)
            if sub_queries:
                print(f"   -> Các câu hỏi phụ: {sub_queries}")
                search_queries.extend(sub_queries)

        # 2. Vector Search (Song song)
        # Mã hóa tất cả câu hỏi thành vector
        query_vectors = self.embedder.encode(search_queries)
        
        # Tìm kiếm trong Milvus cho từng vector
        all_hits = []
        for vec in query_vectors:
            # Tìm topk cho mỗi câu hỏi (có thể giảm k cho query phụ nếu muốn nhanh)
            hits = search(self.collection, vec, topk=topk)
            all_hits.extend(hits)

        # 3. Deduplication (Khử trùng lặp thủ công dựa trên chunk_id)
        # Sử dụng dict để giữ lại hit có điểm cao nhất nếu trùng
        unique_hits_map = {}
        for h in all_hits:
            c_id = h["chunk_id"]
            if c_id not in unique_hits_map:
                unique_hits_map[c_id] = h
            # (Milvus trả về distance/score, tùy metric mà so sánh, ở đây ta cứ giữ cái đầu tiên tìm thấy)
        
        candidates = list(unique_hits_map.values())

        if not candidates:
            return []

        # 4. Rerank (Bước quan trọng nhất để lọc rác)
        print(f"📊 Reranking {len(candidates)} đoạn văn...")
        passages = [h["text"] for h in candidates]
        
        # Rerank dựa trên câu hỏi GỐC (question) để đảm bảo sát nghĩa nhất
        rr_scores = self.reranker.rerank(question, passages)

        # Gán điểm và sort
        for h, s in zip(candidates, rr_scores):
            h["rerank_score"] = float(s)
        
        final_hits = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)

        # Cắt lấy top N tốt nhất
        return final_hits[:rerank_topn]