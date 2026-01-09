from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ===== Vector DB =====
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection: str = "war_chunks"

    # ===== LLM (Groq - OpenAI compatible) =====
    llm_base_url: str = "https://api.groq.com/openai/v1"
    GROQ_API_KEY: str 
    llm_model: str = "llama-3.3-70b-versatile"
    
    #===LLM (Deepseek) =====
    # llm_base_url: str = "https://api.deepseek.com"
    # DEEPSEEK_API_KEY: str
    # llm_model: str = "deep-seek-chat"

    # ===== Local models =====
    embed_model: str = "BAAI/bge-m3"
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    # ===== MinIO =====

    MINIO_ENDPOINT: str = "http://localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "pdf-storage"

    class Config:
        env_file = ".env"

settings = Settings()
# Sử dụng singleton settings trong toàn bộ app