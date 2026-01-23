import asyncio
from typing import List, Dict
from rank_bm25 import BM25Okapi
from app.services.embedding import LocalEmbedder
from app.services.neo4j_store import search
from app.services.rerank import LocalReranker
from app.services.llm_client import openai_client # Giả sử bạn đã export client từ đây
from app.core.settings import settings

class RAGPipeline:
    def __init__(self, embedder: LocalEmbedder, reranker: LocalReranker, all_docs_for_bm25: List[Dict] = None):
        self.embedder = embedder
        self.reranker = reranker
        
        # --- Setup BM25 (Keyword Search) ---
        if all_docs_for_bm25:
            self.bm25_corpus = [doc["text"] for doc in all_docs_for_bm25]
            self.doc_map = all_docs_for_bm25
            tokenized_corpus = [doc.lower().split(" ") for doc in self.bm25_corpus]
            self.bm25 = BM25Okapi(tokenized_corpus)
        else:
            self.bm25 = None
            print("⚠️ Cảnh báo: Không có dữ liệu cho Keyword Search (BM25). Chỉ chạy Vector Search.")

    # --- 1. QUERY PROCESSING (Sinh câu hỏi phụ) ---
    async def _query_processing(self, question: str) -> List[str]:
        """Dùng LLM để tạo ra các biến thể của câu hỏi (Query Expansion)"""
        try:
            # Nếu câu hỏi quá ngắn hoặc quá đơn giản, có thể bỏ qua bước này để tiết kiệm
            system_prompt = "Bạn là trợ lý tìm kiếm. Hãy viết lại câu hỏi sau thành 3 phiên bản khác nhau để tìm kiếm tài liệu tốt hơn. Chỉ trả về các câu hỏi, mỗi câu 1 dòng."
            response = await openai_client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0.5,
                max_tokens=150
            )
            content = response.choices[0].message.content.strip()
            sub_queries = [line.strip("- ").strip() for line in content.split("\n") if line.strip()]
            return [question] + sub_queries # Luôn giữ câu gốc
        except Exception as e:
            print(f"Lỗi Query Processing: {e}")
            return [question]

    # --- 2. HYBRID SEARCH (Vector + Keyword) ---
    def _hybrid_search_single_query(self, query: str, topk: int) -> List[Dict]:
        """Chạy cả Vector và Keyword cho 1 câu hỏi"""
        hits_map = {}

        # A. Semantic Search (Vector)
        qvec = self.embedder.encode([query])[0]
        vector_hits = search(qvec, topk=topk)
        for h in vector_hits:
            if "metadata" not in h or h["metadata"] is None:
                h["metadata"] = {}
            h["metadata"]["source_method"] = "vector"
            hits_map[h["chunk_id"]] = h

        # B. Keyword Search (BM25)
        if self.bm25:
            tokenized_query = query.lower().split(" ")
            scores = self.bm25.get_scores(tokenized_query)
            top_n = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:topk]
            for i in top_n:
                if scores[i] > 0:
                    doc = self.doc_map[i]
                    if doc["chunk_id"] not in hits_map:
                        hits_map[doc["chunk_id"]] = {
                            "chunk_id": doc["chunk_id"],
                            "text": doc["text"],
                            "metadata": {"source_method": "keyword", **doc.get("metadata", {})}
                        }
                    else:
                        # Nếu cả 2 đều tìm thấy -> Tăng độ ưu tiên (tạm thời chưa xử lý ở đây)
                        hits_map[doc["chunk_id"]]["metadata"]["source_method"] = "hybrid"
        
        return list(hits_map.values())

    # --- MAIN FLOW: RUN PIPELINE ---
    async def run(self, original_question: str, topk: int = 5, rerank_topn: int = 3):
        # Bước 1: Query Processing
        # Tạo ra nhiều câu hỏi để "vét" thông tin kỹ hơn
        all_queries = await self._query_processing(original_question)
        print(f"🔍 Queries: {all_queries}")

        # Bước 2: Multi-Query Hybrid Search
        # Tìm kiếm với TẤT CẢ các câu hỏi (Parallel hoặc Loop)
        raw_candidates = []
        seen_ids = set()
        
        for q in all_queries:
            # Với mỗi câu hỏi phụ, tìm kiếm bằng cả Vector và Keyword
            hits = self._hybrid_search_single_query(q, topk=topk)
            for h in hits:
                if h["chunk_id"] not in seen_ids:
                    raw_candidates.append(h)
                    seen_ids.add(h["chunk_id"])

        if not raw_candidates:
            return []

        # Bước 3: Reranking (Chốt hạ)
        # Dùng câu hỏi GỐC để chấm điểm lại toàn bộ kết quả tìm được
        print(f"📊 Reranking {len(raw_candidates)} documents...")
        passages = [h["text"] for h in raw_candidates]
        rr_scores = self.reranker.rerank(original_question, passages)

        for h, s in zip(raw_candidates, rr_scores):
            h["rerank_score"] = float(s)

        final_hits = sorted(raw_candidates, key=lambda x: x["rerank_score"], reverse=True)
        return final_hits[:rerank_topn]
    
    def reload_bm25(self, all_docs: list[dict]):
        """
        Hàm này giúp BM25 học lại từ đầu dựa trên danh sách docs mới nhất.
        """
        if not all_docs:
            print("⚠️ Dữ liệu rỗng, tắt BM25.")
            self.bm25 = None
            self.doc_map = []
            return

        print(f"🔄 Đang cập nhật BM25 với {len(all_docs)} tài liệu mới...")
        self.bm25_corpus = [doc["text"] for doc in all_docs]
        self.doc_map = all_docs # Lưu lại để map ID sau này
        
        # Tokenize và tạo Index mới
        tokenized_corpus = [doc.lower().split(" ") for doc in self.bm25_corpus]
        self.bm25 = BM25Okapi(tokenized_corpus)
        print("✅ BM25 cập nhật thành công!")