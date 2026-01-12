# from fastapi import FastAPI
# from app.api.documents import router as documents_router
# from app.api.query import router as query_router
# from app.core.settings import settings
# from app.api.debug import router as debug_router


# app = FastAPI(title="AI PDF RAG", version="0.1.0")

# @app.get("/health")
# def health():
#     return {"status": "ok", "collection": settings.milvus_collection}

# app.include_router(documents_router)
# app.include_router(query_router)
# app.include_router(debug_router)

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates 
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.documents import router as documents_router
from app.api.query import router as query_router
from app.api.debug import router as debug_router

# 1. Khởi tạo App

app = FastAPI(title="AI PDF RAG System")

# 2. Cấu hình Jinja2 trỏ vào thư mục templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 3. Include các router API cũ
app.include_router(documents_router)
app.include_router(query_router)
app.include_router(debug_router)

# 4. Tạo Route trang chủ (Root /)
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # Trả về file index.html nằm trong thư mục templates
    return templates.TemplateResponse("index.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)