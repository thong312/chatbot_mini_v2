# AI PDF RAG System

A Retrieval-Augmented Generation (RAG) system for querying PDF documents. This project uses local embeddings and reranking with Milvus for vector storage, MinIO for file storage, and an external LLM (Groq) for generation.

## Features
- **PDF Ingestion**: Parses and chunks PDF documents.
- **Vector Search**: Uses Milvus for high-performance vector similarity search.
- **Local Embeddings**: Utilizes `BAAI/bge-m3` for state-of-the-art embeddings.
- **Reranking**: Improves retrieval accuracy with `BAAI/bge-reranker-v2-m3`.
- **Hybrid Storage**: Stores raw files in MinIO and vectors in Milvus.
- **Interactive UI**: Simple web interface for uploading documents and chatting.

## Prerequisites
- **Docker & Docker Compose**: For running Milvus and MinIO.
- **Python 3.10+**
- **uv** (Recommended for dependency management) or `pip`.

## Setup & Installation

### 1. Start Infrastructure
Start the required services (Milvus and MinIO) using Docker Compose.

```bash
docker-compose -f infra/docker-compose.yml up -d
```

This will start:
- **Milvus** (Vector DB) on port `19530`
- **MinIO** (Object Storage) API on port `9000`, Console on `9001`
- **etcd** (Metadata storage for Milvus)

### 2. Backend Configuration
Navigate to the `backend` directory:

```bash
cd backend
```

Create a `.env` file in the `backend` directory with your API keys. You will need a [Groq API Key](https://console.groq.com/).

```ini
# .env
GROQ_API_KEY=your_groq_api_key_here

# Optional overrides (defaults shown)
# MINIO_ENDPOINT=http://localhost:9000
# MINIO_ACCESS_KEY=minioadmin
# MINIO_SECRET_KEY=minioadmin
# MILVUS_HOST=localhost
```

### 3. Install Dependencies

Using `uv` (Fast & Recommended):
```bash
uv sync
```

Or using standard `pip`:
```bash
pip install .
```

## Running the Application

Start the FastAPI backend server:

```bash
# Using uv
uv run uvicorn app.main:app --reload

# Or directly with python if installed via pip
python -m app.main
```

The server will start at `http://localhost:8000`.

## Usage

- **Web Interface**: Open [http://localhost:8000](http://localhost:8000) to upload PDFs and query them.
- **API Documentation**: Open [http://localhost:8000/docs](http://localhost:8000/docs) to explore the Swagger UI.
- **MinIO Console**: Open [http://localhost:9001](http://localhost:9001) (User: `minioadmin`, Pass: `minioadmin`) to view stored files.

## Project Structure

```
├── backend/            # Python FastAPI application
│   ├── app/            # Application source code
│   │   ├── api/        # API endpoints
│   │   ├── core/       # Settings and config
│   │   ├── services/   # Business logic (Chunking, Embedding, Storage)
│   │   └── templates/  # HTML templates
│   ├── pyproject.toml  # Dependency configuration
├── infra/              # Infrastructure configuration (Docker)
│   └── docker-compose.yml
└── README.md           # This file
```