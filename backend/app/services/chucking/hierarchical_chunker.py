from __future__ import annotations

import re
from typing import List, Dict, Optional
from transformers import AutoTokenizer

from app.services.pdf_ingest import normalize_text
# Đảm bảo bạn đang dùng bản sentence_chunker mới nhất tôi đã sửa ở bước trước
from .sentence_chunker import chunk_by_sentences

# --- FIX 1: Cải thiện Regex dọn dẹp ---
# Bắt thêm khoảng trắng thừa quanh dấu gạch ngang: "process - \n ing"
_RE_HYPHEN_LINEBREAK = re.compile(r"(\w)[ \t]*-[ \t]*\n[ \t]*(\w)", flags=re.UNICODE) 
_RE_SINGLE_NL = re.compile(r"(?<!\n)\n(?!\n)")
_RE_MULTI_NL = re.compile(r"\n{3,}")

def _clean_layout_text(t: str) -> str:
    """
    Dọn dẹp text rác từ PDF layout
    """
    if not t:
        return ""
    # Chuẩn hóa xuống dòng Windows
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    # Nối từ bị ngắt dòng: "process-\ning" -> "processing"
    t = _RE_HYPHEN_LINEBREAK.sub(r"\1\2", t)
    # Giữ paragraph break (2 newline) nhưng xóa single newline (thành space)
    t = _RE_MULTI_NL.sub("\n\n", t)
    t = _RE_SINGLE_NL.sub(" ", t)
    # Xóa space thừa
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\n[ \t]+", "\n\n", t).strip()
    return t

def _token_len(tokenizer: AutoTokenizer, text: str) -> int:
    return len(tokenizer.encode(text, add_special_tokens=False))

def chunk_hierarchical(
    pages: List[Dict],
    tokenizer_model: str,
    coarse_target_tokens: int = 1024, # Khuyến nghị: 1024 cho Parent
    coarse_overlap_tokens: int = 200, 
    chunk_size: int = 512,            # Khuyến nghị: 256-512 cho Child
    overlap_sentences: int = 2,
    return_level: str = "both",       # "fine" | "coarse" | "both" | "nested"
) -> List[Dict]:
    """
    Hierarchical Chunking (Đã sửa lỗi Logic):
    1. Pre-process: Biến pages thành danh sách các đoạn văn (Paragraphs) kèm metadata trang.
    2. Coarse Split: Gom các paragraphs lại thành Parent Chunk theo token limit.
    3. Fine Split: Cắt Parent Chunk thành các Child Chunks (câu).
    """
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_model, use_fast=True)
    
    # --- STEP 1: Xây dựng danh sách Paragraphs (Atomic Units) ---
    # Thay vì xử lý string khổng lồ, ta xử lý list các đoạn văn nhỏ
    # Structure: {'text': str, 'tokens': int, 'page': int}
    
    paragraphs = []
    
    for p in pages:
        raw = normalize_text(p["text"]) or ""
        clean = _clean_layout_text(raw)
        if not clean.strip():
            continue
            
        # Tách thành các đoạn nhỏ dựa trên \n\n
        splits = clean.split("\n\n")
        for s in splits:
            s = s.strip()
            if not s: 
                continue
            paragraphs.append({
                "text": s,
                "tokens": _token_len(tokenizer, s),
                "page": p["page"] # Lưu vết trang cho đoạn văn này
            })

    if not paragraphs:
        return []

    # --- STEP 2: Tạo Coarse Chunks (Sliding Window chính xác) ---
    coarse_chunks = []
    
    idx = 0
    while idx < len(paragraphs):
        current_chunk_paras = []
        current_tokens = 0
        start_idx = idx
        
        # Gom paragraph cho đến khi đầy coarse_target_tokens
        while idx < len(paragraphs):
            para = paragraphs[idx]
            # Nếu thêm đoạn này mà lố quá nhiều (ví dụ > 1.2 lần target) thì dừng
            # Hoặc dừng đúng target tùy logic. Ở đây cho phép lố một chút để trọn vẹn paragraph.
            if current_tokens + para["tokens"] > coarse_target_tokens and current_tokens > 0:
                break
            
            current_chunk_paras.append(para)
            current_tokens += para["tokens"]
            idx += 1
            
        # Tạo Coarse Chunk
        full_text = "\n\n".join([p["text"] for p in current_chunk_paras])
        page_start = current_chunk_paras[0]["page"]
        page_end = current_chunk_paras[-1]["page"]
        parent_id = f"parent_{len(coarse_chunks)}"
        
        coarse_chunk = {
            "chunk_id": parent_id,
            "level": "coarse",
            "page_start": page_start,
            "page_end": page_end,
            "token_len": current_tokens,
            "text": full_text
        }
        coarse_chunks.append(coarse_chunk)

        # --- Logic Overlap (Backtrack) ---
        # Nếu đã hết bài thì thoát
        if idx >= len(paragraphs):
            break
            
        # Nếu cần overlap, ta lùi index lại một đoạn
        # Tính ngược từ cuối chunk hiện tại, lùi lại cho đến khi đủ overlap_tokens
        overlap_accum = 0
        backtrack_steps = 0
        
        # Duyệt ngược từ đoạn văn cuối cùng vừa thêm vào
        for i in range(idx - 1, start_idx - 1, -1):
            overlap_accum += paragraphs[i]["tokens"]
            backtrack_steps += 1
            if overlap_accum >= coarse_overlap_tokens:
                break
        
        # Lùi idx lại để chunk sau bắt đầu từ vùng overlap
        # Lưu ý: Nếu chunk quá ngắn (ngắn hơn overlap), ta lùi về start_idx + 1 để tránh kẹt vô tận
        new_idx = idx - backtrack_steps
        if new_idx <= start_idx: 
             # Trường hợp 1 paragraph lớn hơn cả chunk size, buộc phải move next
            idx = max(idx, start_idx + 1)
        else:
            idx = new_idx

    # --- STEP 3: Tạo Fine Chunks (Children) ---
    all_fine_chunks = []
    
    # Nếu chỉ cần Coarse thì return sớm
    if return_level == "coarse":
        return coarse_chunks

    fine_global_idx = 0
    
    for parent in coarse_chunks:
        # Gọi lại hàm sentence split cho nội dung của Parent
        # Lưu ý: Ta giả lập input pages là 1 trang chứa nội dung parent
        # (Chấp nhận việc Fine Chunk sẽ mang page range của Parent)
        
        pseudo_pages = [{
            "text": parent["text"], 
            "page": parent["page_start"] # Tạm lấy page start làm mốc
        }]
        
        children = chunk_by_sentences(
            pages=pseudo_pages,
            tokenizer_model=tokenizer_model,
            chunk_size=chunk_size,
            overlap_sentences=overlap_sentences
        )
        
        for ch in children:
            # Gán Parent ID vào Child
            ch["chunk_id"] = f"child_{fine_global_idx}"
            ch["level"] = "both"
            ch["parent_id"] = parent["chunk_id"]
            # Fix lại page range theo Parent (vì child nằm trong parent)
            ch["page_start"] = parent["page_start"]
            ch["page_end"] = parent["page_end"]
            
            all_fine_chunks.append(ch)
            fine_global_idx += 1

    # --- Return Formatting ---
    if return_level == "nested":
        # Trả về Parent kèm list children bên trong (Dành cho DB NoSQL/JSON)
        nested_chunks = []
        for p in coarse_chunks:
            p["child_chunks"] = [c for c in all_fine_chunks if c["parent_id"] == p["chunk_id"]]
            nested_chunks.append(p)
        return nested_chunks

    elif return_level == "both":
        return coarse_chunks + all_fine_chunks
        
    else: # "fine"
        return all_fine_chunks