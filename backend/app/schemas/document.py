from pydantic import BaseModel

class IngestResponse(BaseModel):
    document_id: str
    chunks_inserted: int
    filename: str | None = None
