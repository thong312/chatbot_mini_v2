from pydantic import BaseModel

class AskRequest(BaseModel):
    question: str
    topk: int = 30
    rerank_topn: int = 7

class AskResponse(BaseModel):
    answer: str
    context: list[dict]
