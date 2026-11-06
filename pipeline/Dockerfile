# ==============================================================================
# Dockerfile - Pipeline Service (CLI ai-library)
# Theo đặc tả Mục 14.6
# ==============================================================================

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libicu-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pipeline/requirements.txt .
RUN pip install --upgrade pip && \
    pip install torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install -r requirements.txt

COPY pipeline/ ./pipeline/
RUN pip install -e ./pipeline

ENTRYPOINT ["ai-library"]
CMD ["--help"]

