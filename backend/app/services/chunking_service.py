import re
from transformers import AutoTokenizer
from app.services.pdf_ingest import normalize_text


LEADER_DOTS = re.compile(r"\.{3,}\s*\d+\s*$")                 #
DOT_GARBAGE_LINE = re.compile(r"^\.*\s*$")                    
PAGE_NUM_LINE = re.compile(r"^\s*\d+\s*$")                   
TOC_HEADING = re.compile(r"^\s*(mục lục|table of contents)\s*$", re.I)

# --- helpers ---
_SENT_SPLIT = re.compile(r"(?<=[\.\!\?。！？])\s+")
_PARA_SPLIT = re.compile(r"\n{2,}")  # paragraph = blank lines

def _split_paragraphs(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    paras = [p.strip() for p in _PARA_SPLIT.split(text) if p.strip()]
    return paras

def _split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    sents = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
    return sents

def _tok_len(tokenizer, text: str) -> int:
    return len(tokenizer.encode(text, add_special_tokens=False))

def _truncate_to_tokens(tokenizer, text: str, max_tokens: int) -> str:
    ids = tokenizer.encode(text, add_special_tokens=False)[:max_tokens]
    return tokenizer.decode(ids).strip()

def clean_pdf_artifacts(text: str) -> str:
    lines = []
    for ln in text.splitlines():
        s = ln.strip()

        # bỏ dòng rỗng
        if not s:
            lines.append("")
            continue

        # bỏ leader dots dạng mục lục
        if LEADER_DOTS.search(s):
            continue

        # bỏ dòng chỉ toàn dấu chấm
        if DOT_GARBAGE_LINE.match(s):
            continue

        # bỏ dòng chỉ có số trang
        if PAGE_NUM_LINE.match(s):
            continue

        # bỏ dòng "Mục lục"
        if TOC_HEADING.match(s):
            continue

        lines.append(ln)

    # gộp lại và giảm bớt newline thừa
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()

def chunk_by_tokens(
    pages: list[dict],
    tokenizer_model: str,
    chunk_size: int = 650,
    overlap_tokens: int = 100,
    max_para_tokens: int = 900,   # đoạn quá dài thì sẽ tách câu
) -> list[dict]:
    """
    Semantic-first chunking:
    - Tách theo paragraph theo từng page -> giữ page provenance.
    - Đóng gói paragraphs vào chunk theo token budget.
    - Nếu paragraph quá dài -> tách câu, rồi đóng gói.
    - Overlap theo tokens (nhưng overlap bằng cách carry một phần text cuối).
    """
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_model, use_fast=True)

    # 1) Build "units": mỗi unit là 1 đoạn (paragraph) kèm page number
    units: list[dict] = []
    for p in pages:
        page_no = int(p.get("page", 1))
        t = normalize_text(p.get("text", ""))
        if not t:
            continue

        for para in _split_paragraphs(t):
            # Nếu đoạn quá dài: tách câu
            if _tok_len(tokenizer, para) > max_para_tokens:
                sents = _split_sentences(para)
                # nếu vẫn không tách được (text kỳ), fallback truncate
                if len(sents) <= 1:
                    para = _truncate_to_tokens(tokenizer, para, max_para_tokens)
                    units.append({"page": page_no, "text": para})
                else:
                    for s in sents:
                        if s:
                            units.append({"page": page_no, "text": s})
            else:
                units.append({"page": page_no, "text": para})

    # 2) Pack units into chunks by token budget
    chunks: list[dict] = []
    idx = 0

    cur_texts: list[str] = []
    cur_pages: list[int] = []
    cur_tokens = 0

    def flush():
        nonlocal idx, cur_texts, cur_pages, cur_tokens
        if not cur_texts:
            return
        text = "\n\n".join(cur_texts).strip()
        if text:
            chunks.append({
                "chunk_id": f"c{idx}",
                "page_start": min(cur_pages) if cur_pages else 1,
                "page_end": max(cur_pages) if cur_pages else 1,
                "text": text,
            })
            idx += 1
        cur_texts, cur_pages, cur_tokens = [], [], 0

    # Overlap: giữ phần tail của chunk trước theo token budget
    def make_overlap_text(text: str) -> str:
        if overlap_tokens <= 0:
            return ""
        ids = tokenizer.encode(text, add_special_tokens=False)
        tail = ids[-min(overlap_tokens, len(ids)):]
        return tokenizer.decode(tail).strip()

    for u in units:
        t = u["text"]
        page_no = u["page"]
        t_tokens = _tok_len(tokenizer, t)

        # Nếu 1 unit đã lớn hơn chunk_size: truncate để không vỡ
        if t_tokens > chunk_size:
            t = _truncate_to_tokens(tokenizer, t, chunk_size)
            t_tokens = _tok_len(tokenizer, t)

        # nếu thêm vào vượt quá budget -> flush chunk hiện tại
        if cur_tokens > 0 and (cur_tokens + t_tokens) > chunk_size:
            prev_text = "\n\n".join(cur_texts)
            flush()

            # tạo overlap chunk mới từ tail text trước
            overlap_text = make_overlap_text(prev_text)
            if overlap_text:
                cur_texts = [overlap_text]
                cur_pages = [page_no]  # provenance: overlap không chắc page, tạm gán page hiện tại
                cur_tokens = _tok_len(tokenizer, overlap_text)

        # add unit
        cur_texts.append(t)
        cur_pages.append(page_no)
        cur_tokens += t_tokens

    flush()
    return chunks
