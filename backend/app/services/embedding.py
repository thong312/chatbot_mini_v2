from FlagEmbedding import FlagModel
import numpy as np

class LocalEmbedder:
    def __init__(self, model_name: str):
        # FlagModel sẽ tự chọn device phù hợp (cpu/gpu) tuỳ torch
        self.model = FlagModel(
            model_name,
            query_instruction_for_retrieval="Represent this sentence for searching relevant passages:",
            use_fp16=True,
        )

        # cache dim một lần để khỏi encode khi import nhiều lần
        self._dim = None

    @property
    def dim(self) -> int:
        if self._dim is None:
            v = self.encode(["dimension_probe"])[0]
            self._dim = len(v)
        return self._dim

    def encode(self, texts: list[str]) -> list[list[float]]:
        # KHÔNG truyền normalize_embeddings vào encode (tránh lỗi phiên bản)
        emb = self.model.encode(texts)
        # emb có thể là numpy array / list -> đưa về numpy để normalize
        arr = np.array(emb, dtype=np.float32)
        # normalize L2 để dùng cosine/IP ổn định
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        arr = arr / np.clip(norms, 1e-12, None)
        return arr.tolist()
