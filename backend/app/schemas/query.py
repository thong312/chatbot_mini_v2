# app/schemas/query.py

from pydantic import BaseModel
from typing import List, Optional, Dict

class Message(BaseModel):
    role: str
    content: str

class AskRequest(BaseModel):
    question: str
    
    # --- THÊM DÒNG NÀY ĐỂ SỬA LỖI ---
    session_id: Optional[str] = None 
    # -------------------------------

    topk: int = 30
    rerank_topn: int = 7
    
    # Trường history giờ không bắt buộc nữa vì server tự lấy từ DB
    # Bạn có thể để rỗng hoặc xóa dòng này cũng được
    history: List[Message] = [] 

class AskResponse(BaseModel):
    answer: str
    context: List[Dict]