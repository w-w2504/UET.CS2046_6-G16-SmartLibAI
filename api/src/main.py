import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.config import settings
from src.middleware.contract import ContractMiddleware, error_response
from src.middleware.request_id import RequestIDMiddleware
from src.middleware.search_deadline import SearchDeadlineMiddleware
from src.routes import health, books, search, recommend, reader, qa
from src.services.catalog import CatalogError
from src.schemas.common import Filters

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
app.add_middleware(ContractMiddleware)
app.add_middleware(SearchDeadlineMiddleware)
app.add_middleware(RequestIDMiddleware)


@app.middleware("http")
async def api_no_store(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/v1/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(CatalogError)
async def catalog_exception_handler(request: Request, exc: CatalogError):
    req_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": exc.message, "field": exc.field, "module": exc.module, "request_id": req_id}, headers={"X-Request-ID": req_id, "Cache-Control": "no-store"})


# 3. Chuẩn hóa Exception Handlers theo đặc tả Mục 12.3 & 14.1
# Thứ tự trường body tại §12.4. Không dùng thứ tự kế thừa của model.
BODY_FIELD_ORDER = {
    "/api/v1/search": ("q", "k", "filters", "snapshot_id"),
    "/api/v1/recommend": ("seed_book_ids", "exclude_book_ids", "k", "filters", "snapshot_id"),
    "/api/v1/qa": ("book_id", "question", "snapshot_id"),
}
FILTER_FIELD_ORDER = tuple(Filters.model_fields)


def validation_order(location, body_fields, query_fields):
    source, *fields = location or ("",)
    order = {"body": body_fields, "query": query_fields}.get(source, ())
    key = []
    for field in fields:
        if isinstance(field, int):
            key.append((field, ""))
        elif field in order:
            key.append((order.index(field), ""))
        else:
            key.append((len(order), field))
        order = FILTER_FIELD_ORDER if source == "body" and field == "filters" else ()
    # POST operations define body fields and no query fields in the contract.
    sources = ("path", "body", "query") if body_fields else ("path", "query", "body")
    return (sources.index(source) if source in sources else len(sources), key)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Bắt lỗi 422 cú pháp/kiểu đầu vào và format theo ErrorResponse."""
    req_id = getattr(request.state, "request_id", "unknown")
    errors = [*exc.errors(), *getattr(request.state, "boundary_errors", ())]
    if any(error["type"] == "json_invalid" for error in errors):
        return error_response(req_id, 400, "invalid_json", "Nội dung JSON không hợp lệ")
    body_fields = BODY_FIELD_ORDER.get(request.url.path.rstrip("/"), ())
    query_fields = getattr(request.state, "query_fields", ())
    first = min(errors, key=lambda error: validation_order(error.get("loc", ()), body_fields, query_fields))
    loc = first.get("loc", ())
    field = ".".join(map(str, loc[1:] if loc and loc[0] in {"body", "query", "path"} else loc))
    return error_response(req_id, 422, "invalid_input", "Dữ liệu đầu vào không hợp lệ", field or None)


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
            message = "Đã xảy ra lỗi khi xử lý yêu cầu"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": code,
            "message": message,
            "field": field,
            "module": module,
            "request_id": req_id,
        },
        headers={**(exc.headers or {}), "X-Request-ID": req_id, "Cache-Control": "no-store"}
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
        headers={"X-Request-ID": req_id, "Cache-Control": "no-store"}
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

