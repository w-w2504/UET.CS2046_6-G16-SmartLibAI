import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.config import settings
from src.middleware.request_id import RequestIDMiddleware
from src.routes import health, books, search, recommend, reader, qa

# Thiết lập logging chuẩn
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("smartlib.api")

app = FastAPI(
    title="AI Thư Viện (SmartLib AI) API",
    description="Hệ thống API backend cho đồ án môn Trí tuệ nhân tạo (CS2046)",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json"
)

# 1. Cấu hình CORS
origins = [
    settings.PUBLIC_ORIGIN,
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Gắn Middleware X-Request-ID
app.add_middleware(RequestIDMiddleware)


# 3. Chuẩn hóa Exception Handlers theo đặc tả Mục 12.3 & 14.1
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Bắt lỗi 422 cú pháp/kiểu đầu vào và format theo ErrorResponse."""
    req_id = getattr(request.state, "request_id", "unknown")
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    field_loc = ".".join(str(loc) for loc in first_error.get("loc", []) if loc != "body")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "invalid_input",
            "message": f"Dữ liệu đầu vào không hợp lệ: {first_error.get('msg', 'Giá trị không đúng')}",
            "field": field_loc or None,
            "module": None,
            "request_id": req_id,
        },
        headers={"X-Request-ID": req_id}
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Bắt các lỗi HTTP status và chuẩn hóa cấu trúc JSON ErrorResponse."""
    req_id = getattr(request.state, "request_id", "unknown")
    
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", "http_error")
        message = exc.detail.get("message", "Đã xảy ra lỗi khi xử lý yêu cầu")
        field = exc.detail.get("field", None)
        module = exc.detail.get("module", None)
    else:
        field = None
        module = None
        if exc.status_code == 404:
            code = "resource_not_found"
            message = "Tài nguyên hoặc đường dẫn không tồn tại"
        elif exc.status_code == 405:
            code = "method_not_allowed"
            message = "Phương thức HTTP không được hỗ trợ"
        elif exc.status_code == 413:
            code = "payload_too_large"
            message = "Kích thước request body vượt giới hạn cho phép"
        elif exc.status_code == 415:
            code = "unsupported_media_type"
            message = "Định dạng Content-Type không được hỗ trợ"
        elif exc.status_code == 429:
            code = "rate_limited"
            message = "Đã vượt quá giới hạn tần suất yêu cầu"
        else:
            code = f"http_{exc.status_code}"
            message = str(exc.detail)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": code,
            "message": message,
            "field": field,
            "module": module,
            "request_id": req_id,
        },
        headers={"X-Request-ID": req_id}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Bắt mọi ngoại lệ chưa phân loại, trả 500 và che giấu stack trace."""
    req_id = getattr(request.state, "request_id", "unknown")
    logger.exception(f"Unhandled error for request {req_id}: {exc}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "internal_error",
            "message": "Lỗi máy chủ nội bộ, vui lòng thử lại sau",
            "field": None,
            "module": None,
            "request_id": req_id,
        },
        headers={"X-Request-ID": req_id}
    )


# 4. Gắn các Router API v1
api_v1_prefix = "/api/v1"
app.include_router(health.router, prefix=api_v1_prefix)
app.include_router(books.router, prefix=api_v1_prefix)
app.include_router(search.router, prefix=api_v1_prefix)
app.include_router(recommend.router, prefix=api_v1_prefix)
app.include_router(reader.router, prefix=api_v1_prefix)
app.include_router(qa.router, prefix=api_v1_prefix)


@app.get("/")
async def root():
    return {
        "service": "AI Thư Viện (SmartLib AI) API",
        "version": "0.1.0",
        "health_check": "/api/v1/health",
        "docs": "/docs"
    }

