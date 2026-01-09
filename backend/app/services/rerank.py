from FlagEmbedding import FlagReranker

class LocalReranker:
    def __init__(self, model_name: str):
        self.reranker = FlagReranker(model_name, use_fp16=True)

    def rerank(self, query: str, passages: list[str]) -> list[float]:
        pairs = [[query, p] for p in passages]
        scores = self.reranker.compute_score(pairs)
        if isinstance(scores, float):
            return [float(scores)]
        return [float(x) for x in scores]
