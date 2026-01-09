import re
from transformers import AutoTokenizer
from app.services.pdf_ingest import normalize_text
# from app.utils.split_sentence import split_sentences # Chúng ta sẽ viết lại hàm này tốt hơn ngay bên dưới

_END_PUNCT = (".", "!", "?", "…", "。", "！", "？")

# Danh sách viết tắt phổ biến cần tránh cắt câu (có thể bổ sung thêm)
_ABBREVIATIONS = {"tp.", "mr.", "mrs.", "dr.", "th s.", "ts.", "prof.", "vol.", "p.", "pp.", "st."}

def advanced_split_sentences(text: str) -> list[str]:
    """
    Tách câu thông minh hơn:
    - Không tách ở số thập phân (3.5)
    - Không tách ở các từ viết tắt thông dụng (Tp. HCM)
    - Giữ lại dấu câu ở cuối câu.
    """
    if not text:
        return []
    
    # Regex lookbehind: Tách tại dấu . ! ? NHƯNG
    # (?<!\d)  : Không phải đứng sau số (tránh 3.5)
    # (?<!Tp)  : Không phải đứng sau từ viết tắt (ví dụ mẫu) -> Cách này thủ công, nên dùng regex tổng quát hơn dưới đây:
    
    # Pattern: Tách khi gặp dấu kết thúc câu, theo sau là khoảng trắng và ký tự in hoa (dấu hiệu câu mới)
    # Hoặc kết thúc chuỗi.
    # Pattern này bảo vệ số thực và các trường hợp thường gặp.
    pattern = r'(?<=[.!?…])\s+(?=[A-ZĂÂĐÊÔƠƯÁÀẢÃẠẮẰẲẴẶẤẦẨẪẬÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢÚÙỦŨỤỨỪỬỮỰÝỲỶỸỴ])'
    
    # Bước 1: Tách sơ bộ dựa trên cấu trúc ngữ pháp
    parts = re.split(pattern, text)
    
    final_sentences = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Kiểm tra kỹ hơn các trường hợp viết tắt bị tách sai nếu cần
        final_sentences.append(part)
        
    return final_sentences

def _looks_complete(sentence: str) -> bool:
    """
    Kiểm tra xem câu đã thực sự kết thúc chưa.
    Logic cũ: chỉ check endswith punctuation -> Sai khi gặp số '3.' hoặc 'Tp.'
    """
    s = sentence.strip()
    if not s:
        return True
        
    # 1. Phải kết thúc bằng dấu câu chuẩn
    if not s.endswith(_END_PUNCT):
        return False
        
    # 2. Kiểm tra ký tự liền trước dấu câu
    # Lấy token cuối cùng (bỏ dấu câu)
    last_word = re.split(r'\s+', s[:-1])[-1].lower() + s[-1] # vd: "tp."
    
    # Nếu kết thúc là số + dấu chấm (vd: "ngày 3.") -> Khả năng cao là ngày tháng hoặc số liệu bị ngắt -> False (để nối tiếp)
    # Regex check: số + chấm ở cuối chuỗi (vd: "12.")
    if re.search(r'\d\.$', s):
        return False

    # 3. Nếu kết thúc là từ viết tắt (vd: "Tp.") -> False
    if last_word in _ABBREVIATIONS:
        return False

    return True

def chunk_by_sentences(
    pages: list[dict],
    tokenizer_model: str,
    chunk_size: int = 500,
    overlap_sentences: int = 2,
):
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_model, use_fast=True)

    chunks = []
    idx = 0
    buffer: list[str] = []
    buffer_tokens = 0
    buffer_pages: list[int] = []

    def tok_len(s: str) -> int:
        return len(tokenizer.encode(s, add_special_tokens=False))

    def flush():
        nonlocal idx, buffer, buffer_tokens, buffer_pages
        if not buffer:
            return

        text = " ".join(buffer).strip()
        chunks.append({
            "chunk_id": f"sent_{idx}",
            "page_start": min(buffer_pages) if buffer_pages else 0,
            "page_end": max(buffer_pages) if buffer_pages else 0,
            "token_len": buffer_tokens,
            "sentence_count": len(buffer),
            "text": text,
        })
        idx += 1

        # Logic Overlap: Giữ lại N câu cuối cùng
        if overlap_sentences > 0 and len(buffer) > overlap_sentences:
            # Chỉ giữ lại phần overlap
            buffer[:] = buffer[-overlap_sentences:]
            buffer_pages[:] = buffer_pages[-overlap_sentences:]
            # Tính lại token cho buffer mới (quan trọng!)
            buffer_tokens = sum(tok_len(s) for s in buffer)
        elif overlap_sentences > 0:
            # Nếu buffer hiện tại nhỏ hơn overlap, giữ nguyên buffer (không clear)
            pass 
        else:
            buffer.clear()
            buffer_pages.clear()
            buffer_tokens = 0

    carry = ""  

    for p in pages:
        text = normalize_text(p["text"])
        if not text:
            continue

        # --- XỬ LÝ NỐI TRANG (FIX MẤT CHỮ) ---
        if carry:
            # Kiểm tra hyphenation: Nếu carry kết thúc bằng "-" (vd: "process-")
            if carry.endswith("-"):
                # Nối liền: "process-" + "ing" -> "processing"
                # Cần bỏ dấu "-" đi
                text = (carry[:-1] + text).strip()
            else:
                # Nối thường: Thêm dấu cách
                text = (carry + " " + text).strip()
            carry = ""

        # Dùng hàm tách câu xịn hơn
        sents = advanced_split_sentences(text)

        # Logic giữ lại câu chưa hoàn chỉnh ở cuối trang
        if sents and not _looks_complete(sents[-1]):
            carry = sents.pop(-1)

        for sent in sents:
            sent = sent.strip()
            if not sent:
                continue

            tlen = tok_len(sent)

            # Check flush TRƯỚC khi append để đảm bảo chunk_size không bị vượt quá nhiều
            # Nhưng quan trọng: Logic cũ append rồi mới flush ở vòng sau có thể gây mất đồng bộ overlap
            # Logic mới: Nếu thêm câu này mà vượt quá -> Flush buffer hiện tại -> Tạo buffer mới (có overlap) -> Append câu này vào buffer mới
            if buffer and (buffer_tokens + tlen > chunk_size):
                flush()
                # Sau khi flush, buffer đã chứa các câu overlap (ví dụ câu A, B).
                # Giờ ta append câu hiện tại (C) vào -> buffer = [A, B, C]
            
            buffer.append(sent)
            buffer_tokens += tlen
            buffer_pages.append(p["page"])

    # Xử lý phần carry còn sót lại ở trang cuối cùng
    if carry.strip():
        # Coi như 1 câu cuối
        sent = carry.strip()
        tlen = tok_len(sent)
        if buffer and (buffer_tokens + tlen > chunk_size):
            flush()
        buffer.append(sent)
        buffer_tokens += tlen
        buffer_pages.append(pages[-1]["page"] if pages else 1)

    flush() # Flush lần cuối
    return chunks