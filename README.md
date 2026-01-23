# CHAT A.I+

A Retrieval-Augmented Generation (RAG) system for querying PDF documents. This project uses local embeddings and reranking with **Neo4j** for vector and graph storage (including chat history), **MinIO** for file storage, and external LLMs (**Groq** & **SambaNova**) for generation and routing.

## Features
- **PDF Ingestion**: Advanced parsing with hierarchical chunking (Parent/Child) for better context.
- **Hybrid Search**: Combines Neo4j vector similarity search with BM25 keyword search.
- **Intelligent Routing**: Automatically classifies queries using an LLM router.
- **Graph-Based Storage**: Uses Neo4j to store document chunks, relationships, and chat history.
- **Local Embeddings**: Utilizes `BAAI/bge-m3` for high-quality multilingual embeddings.
- **Reranking**: Enhances precision with `BAAI/bge-reranker-v2-m3`.
- **Chat History**: Persistent session management using Neo4j graph relationships.
- **Modular UI**: Modern, responsive frontend built with ES Modules and Tailwind CSS.

## Prerequisites
- **Docker & Docker Compose**: For running Neo4j and MinIO.
- **Python 3.10+**
- **uv** (Recommended for dependency management) or `pip`.

## Setup & Installation

### 1. Start Infrastructure
Start the required services (Neo4j and MinIO) using Docker Compose.

```bash
docker-compose -f infra/docker-compose.yml up -d
```

This will start:
- **Neo4j** (Vector & Graph DB) on ports `7474` (Console) & `7687` (Bolt)
- **MinIO** (Object Storage) on `9000` (API) & `9001` (Console)

### 2. Backend Configuration
Navigate to the `backend` directory:

```bash
cd backend
```

Create a `.env` file in the `backend` directory with your API keys.

```ini
# .env

# LLM Providers
GROQ_API_KEY=your_groq_api_key_here
AGENT_API_KEY=your_sambanova_api_key_here

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# MinIO Configuration (Optional overrides, defaults shown)
# MINIO_ENDPOINT=http://localhost:9000
# MINIO_ACCESS_KEY=minioadmin
# MINIO_SECRET_KEY=minioadmin
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
- **Neo4j Console**: Open [http://localhost:7474](http://localhost:7474) (User: `neo4j`, Pass: `password`) to explore the graph data.
- **MinIO Console**: Open [http://localhost:9001](http://localhost:9001) (User: `minioadmin`, Pass: `minioadmin`) to view stored files.

## Project Structure

```
├── backend/            # Python FastAPI application
│   ├── app/            # Application source code
│   │   ├── api/        # API endpoints (query, documents, debug)
│   │   ├── core/       # Settings and global state
│   │   ├── services/   # Business logic (RAG pipeline, Neo4j store, MinIO, etc.)
│   │   ├── schemas/    # Pydantic models
│   │   └── utils/      # Helper functions
│   ├── static/         # Frontend assets (JS modules, CSS)
│   ├── templates/      # HTML templates
│   ├── pyproject.toml  # Dependency configuration
├── infra/              # Infrastructure configuration (Docker)
│   └── docker-compose.yml
└── README.md           # This file
```
