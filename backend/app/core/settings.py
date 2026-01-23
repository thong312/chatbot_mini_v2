from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ===== Neo4j =====
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_database: str = "neo4j" # Default database

    # ===== LLM (Groq - OpenAI compatible) =====
    llm_base_url: str = "https://api.groq.com/openai/v1"
    GROQ_API_KEY: str 
    llm_model: str = "llama-3.3-70b-versatile"
    
    #===LLM (Deepseek) =====
    llm_agent_base_url: str = "https://api.sambanova.ai/v1"
    AGENT_API_KEY: str
    llm_agent_model: str = "Llama-3.3-Swallow-70B-Instruct-v0.4"

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
        extra="ignore"

settings = Settings()
# Sử dụng singleton settings trong toàn bộ app