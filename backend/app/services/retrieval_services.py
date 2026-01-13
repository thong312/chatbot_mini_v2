import time
from typing import List, Dict
from rank_bm25 import BM25Okapi
from app.services.embedding import LocalEmbedder
from app.services.milvus_store import search
from app.services.rerank import LocalReranker

# --- 1. SIMILARITY SEARCH (Vector Search Thuần) ---
class VectorRetriever:
    def __init__(self, collection, embedder: LocalEmbedder):
        self.collection = collection
        self.embedder = embedder

    def search(self, query: str, topk: int = 10) -> List[Dict]:
        """Chỉ tìm kiếm dựa trên vector (Nhanh nhất)"""
        qvec = self.embedder.encode([query])[0]
        hits = search(self.collection, qvec, topk=topk)
        return hits

# --- 2. KEYWORD SEARCH (BM25 - Tìm từ khóa chính xác) ---
class KeywordRetriever:
    def __init__(self, all_documents: List[str]):
        """
        Lưu ý: Với ứng dụng Local nhỏ (<10k chunks), ta có thể load text vào RAM để chạy BM25.
        Nếu dữ liệu lớn, cần dùng ElasticSearch hoặc Milvus Sparse Vector.
        """
        tokenized_corpus = [doc.split(" ") for doc in all_documents]
        self.bm25 = BM25Okapi(tokenized_corpus)
        self.documents = all_documents

    def search(self, query: str, topk: int = 10) -> List[Dict]:
        tokenized_query = query.split(" ")
        # Lấy top k văn bản khớp từ khóa nhất
        scores = self.bm25.get_scores(tokenized_query)
        top_n_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:topk]
        
        results = []
        for i in top_n_indices:
            # Lưu ý: Ở đây ta giả lập cấu trúc trả về giống Milvus để dễ gộp
            results.append({
                "chunk_id": f"bm25_{i}", # Cần mapping ID thực tế nếu có
                "text": self.documents[i],
                "score": scores[i],
                "metadata": {"source": "keyword_search"}
            })
        return results

# --- 3. HYBRID SEARCH (Kết hợp Vector + Keyword + Rerank) ---
class HybridRetriever:
    def __init__(self, vector_retriever: VectorRetriever, reranker: LocalReranker):
        self.vector_retriever = vector_retriever
        self.reranker = reranker

    def _reciprocal_rank_fusion(self, list_of_list_ranks, k=60):
        """Thuật toán RRF để gộp kết quả từ nhiều nguồn (Vector + Keyword)"""
        fused_scores = {}
        for rank_list in list_of_list_ranks:
            for rank, item in enumerate(rank_list):
                doc_content = item["text"] # Dùng nội dung làm key định danh (hoặc dùng ID)
                if doc_content not in fused_scores:
                    fused_scores[doc_content] = {"doc": item, "score": 0}
                fused_scores[doc_content]["score"] += 1 / (k + rank)
        
        # Sắp xếp lại theo điểm RRF
        sorted_results = sorted(fused_scores.values(), key=lambda x: x["score"], reverse=True)
        return [item["doc"] for item in sorted_results]

    async def search(self, query: str, topk: int = 10, rerank_topn: int = 5):
        # 1. Vector Search (Semantic)
        vector_hits = self.vector_retriever.search(query, topk=topk * 2)
        
        # 2. Keyword Search (Optional - Ở đây ta giả lập hoặc bỏ qua nếu chưa có full text)
        # Nếu muốn làm chuẩn, bạn cần fetch toàn bộ text từ Milvus ra để build BM25 (tốn RAM),
        # hoặc đơn giản là dùng cơ chế Rerank làm bộ lọc Hybrid.
        
        # Ở cấp độ đơn giản cho dự án này, HYBRID hiệu quả nhất là:
        # Vector Search (Lấy rộng) -> Rerank (Lọc kỹ)
        # Vì Reranker hoạt động như một bộ Hybrid (hiểu cả từ khóa và ngữ nghĩa)
        
        # 3. Rerank
        # Gộp kết quả (nếu có nhiều nguồn)
        candidates = vector_hits 
        
        # Khử trùng lặp
        seen_text = set()
        unique_candidates = []
        for c in candidates:
            if c["text"] not in seen_text:
                unique_candidates.append(c)
                seen_text.add(c["text"])

        if not unique_candidates:
            return []

        # Chấm điểm lại bằng Cross-Encoder (Đây là bước quan trọng nhất của Hybrid)
        passages = [h["text"] for h in unique_candidates]
        rr_scores = self.reranker.rerank(query, passages)
        
        for h, s in zip(unique_candidates, rr_scores):
            h["rerank_score"] = float(s)
            
        final_hits = sorted(unique_candidates, key=lambda x: x["rerank_score"], reverse=True)
        return final_hits[:rerank_topn]