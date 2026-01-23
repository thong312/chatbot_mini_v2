# app/services/chat_history.py

from typing import List, Dict
from app.services.neo4j_store import get_driver, settings

# 1. Cấu hình (đã dùng chung trong neo4j_store)

# 2. Hàm lấy lịch sử chat
async def get_chat_history(session_id: str, limit: int = 6) -> List[Dict]:
    """Lấy k tin nhắn gần nhất của một phiên chat"""
    driver = get_driver()
    query = """
    MATCH (s:Session {session_id: $session_id})-[:HAS_MESSAGE]->(m:Message)
    RETURN m.role as role, m.content as content, m.timestamp as timestamp
    ORDER BY m.timestamp ASC
    """
    
    # Neo4j driver is sync mostly, but we are in async function. 
    # For high load, we might need async driver, but standard driver is fine for now.
    # We will just run it synchronously.
    
    try:
        with driver.session(database=settings.neo4j_database) as session:
            result = session.run(query, session_id=session_id)
            messages = [{"role": r["role"], "content": r["content"]} for r in result]
            
            # Return last 'limit' messages
            return messages[-limit:]
    except Exception as e:
        print(f"Error fetching chat history: {e}")
        return []

# 3. Hàm lưu tin nhắn mới
async def add_message_to_history(session_id: str, role: str, content: str):
    """Thêm 1 tin nhắn vào session"""
    driver = get_driver()
    query = """
    MERGE (s:Session {session_id: $session_id})
    CREATE (m:Message {role: $role, content: $content, timestamp: timestamp()})
    CREATE (s)-[:HAS_MESSAGE]->(m)
    """
    
    try:
        with driver.session(database=settings.neo4j_database) as session:
            session.run(query, session_id=session_id, role=role, content=content)
    except Exception as e:
        print(f"Error saving chat history: {e}")
