# app/services/chat_history.py

import motor.motor_asyncio
from app.core.settings import settings
from typing import List, Dict

# 1. Cấu hình kết nối (Nên đưa URL vào settings, ở đây mình để cứng demo)
# Chuỗi kết nối: mongodb://user:pass@host:port
MONGO_DETAILS = "mongodb://root:example@localhost:27017" 

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
database = client.rag_chatbot
history_collection = database.get_collection("conversations")

# 2. Hàm lấy lịch sử chat
async def get_chat_history(session_id: str, limit: int = 6) -> List[Dict]:
    """Lấy k tin nhắn gần nhất của một phiên chat"""
    doc = await history_collection.find_one({"session_id": session_id})
    if doc:
        # Lấy 6 tin nhắn cuối cùng để tiết kiệm token
        return doc.get("messages", [])[-limit:]
    return []

# 3. Hàm lưu tin nhắn mới
async def add_message_to_history(session_id: str, role: str, content: str):
    """Thêm 1 tin nhắn vào mảng messages của session đó"""
    new_msg = {"role": role, "content": content}
    
    # Dùng lệnh $push của Mongo để thêm vào mảng
    # upsert=True nghĩa là: Nếu session_id chưa có thì tự tạo mới
    await history_collection.update_one(
        {"session_id": session_id},
        {"$push": {"messages": new_msg}},
        upsert=True
    )