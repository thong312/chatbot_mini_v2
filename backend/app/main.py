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


# main.py
import phoenix as px
from openinference.instrumentation.openai import OpenAIInstrumentor

# --- THÊM CÁC IMPORT NÀY ĐỂ CẤU HÌNH ĐƯỜNG DẪN ---
from opentelemetry import trace as trace_api
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# 1. Khởi động Phoenix Server
session = px.launch_app()

# 2. CẤU HÌNH "DÂY CÁP" (TRACER PROVIDER)
# Mặc định Phoenix chạy ở cổng 6006, endpoint nhận dữ liệu là /v1/traces
endpoint = "http://127.0.0.1:6006/v1/traces"
tracer_provider = trace_sdk.TracerProvider()
span_exporter = OTLPSpanExporter(endpoint=endpoint)
span_processor = SimpleSpanProcessor(span_exporter)
tracer_provider.add_span_processor(span_processor)

# Đặt Tracer này làm mặc định cho toàn bộ ứng dụng
trace_api.set_tracer_provider(tracer_provider)

# 3. Gắn máy theo dõi vào thư viện OpenAI
# Lúc này nó đã biết phải gửi dữ liệu đi đâu (về Phoenix 6006)
OpenAIInstrumentor().instrument()

# ... (Các phần code FastAPI ở dưới giữ nguyên) ...

# ... (Các phần import FastAPI và khởi tạo app ở dưới giữ nguyên) ...
# ...

# ... Code FastAPI của bạn ở dưới ...
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