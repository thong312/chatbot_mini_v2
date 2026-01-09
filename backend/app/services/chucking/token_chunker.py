# app/services/chunking/token_chunker.py
from transformers import AutoTokenizer
from app.services.pdf_ingest import normalize_text

def chunk_by_tokens_per_page(
    pages: list[dict],
    tokenizer_model: str,
    chunk_size: int = 500,
    overlap: int = 80,
):
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_model, use_fast=True)
    chunks = []
    idx = 0

    for p in pages:
        text = normalize_text(p["text"])
        if not text:
            continue

        tokens = tokenizer.encode(text, add_special_tokens=False)
        n = len(tokens)
        start = 0

        while start < n:
            end = min(start + chunk_size, n)
            chunk_tokens = tokens[start:end]
            chunk_text = tokenizer.decode(chunk_tokens).strip()

            if chunk_text:
                chunks.append({
                    "chunk_id": f"tok_{idx}",
                    "page_start": p["page"],
                    "page_end": p["page"],
                    "token_len": len(chunk_tokens),
                    "text": chunk_text,
                })
                idx += 1

            if end == n:
                break
            start = max(0, end - overlap)

    return chunks
