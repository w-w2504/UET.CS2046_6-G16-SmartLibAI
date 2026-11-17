# ==============================================================================
# Dockerfile - API Backend (FastAPI + PyICU + PyTorch CPU + FAISS)
# Theo đặc tả Mục 2.1 & 14.5
# ==============================================================================

FROM python:3.11-slim

# Thiết lập biến môi trường Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# Cài đặt các gói hệ thống cần thiết cho PyICU, FAISS và build C/C++
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libicu-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt Python dependencies
COPY api/requirements.txt ./requirements.txt
COPY pipeline/requirements-embedding.txt ./requirements-embedding.txt
RUN pip install -r requirements.txt -r requirements-embedding.txt && pip check

COPY pipeline/pyproject.toml pipeline/README.md /tmp/smartlib-pipeline/
COPY pipeline/ai_library/ /tmp/smartlib-pipeline/ai_library/
RUN pip install --no-deps /tmp/smartlib-pipeline && pip check && rm -rf /tmp/smartlib-pipeline

# Sao chép mã nguồn API
COPY api/src/ ./src/

# Mở cổng API nội bộ
EXPOSE 8000

# Chạy Uvicorn với 1 worker theo quy định đặc tả (Mục 2.1)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

