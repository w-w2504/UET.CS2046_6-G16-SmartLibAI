# AI Thư Viện (SmartLib AI) - Hệ thống Web AI Thư Viện

> **BTL môn học:** Trí tuệ nhân tạo (CS2046)  
> **Phiên bản:** 0.1 • Tháng 11/2026  
> **Tài liệu đặc tả chi tiết:** [`documents/SPEC.md`](documents/SPEC.md)

---

## 1. Giới thiệu tổng quan

Hệ thống **AI Thư Viện** cung cấp nền tảng số hóa danh mục sách và đọc trực tuyến kết hợp ba tính năng AI cốt lõi:
1. **Tìm kiếm ngữ nghĩa (Semantic Search):** Tìm sách tiếng Việt theo nhu cầu tự nhiên, kết hợp lọc tác giả, thể loại và trạng thái có toàn văn. Baseline đối chuẩn: `BM25`.
2. **Gợi ý theo nội dung (Content-based Recommendation):** Gợi ý tác phẩm phù hợp từ 1–3 cuốn sách sở thích, loại trừ các tác phẩm bị ẩn, cung cấp lý do gợi ý minh bạch (`shared_topic`, `shared_genre`, `content_similarity`). Baseline đối chuẩn: `TF-IDF & cùng thể loại`.
3. **Hỏi đáp có dẫn chứng (Evidence-grounded RAG QA):** Hỏi đáp độc lập trong đúng một ấn bản (`book_id`) đang đọc, trích dẫn chính xác đoạn văn (`citations`), từ chối trả lời nếu thiếu căn cứ (`insufficient_evidence`).

---

## 2. Cấu trúc thư mục dự án

```text
UET.CS2046_6-G16-SmartLibAI/
├── .env.example               # Mẫu biến môi trường cho Docker & Local
├── .gitignore                 # Bỏ qua dependencies, secrets, models, snapshots
├── Caddyfile                  # Cấu hình Reverse Proxy HTTPS & phục vụ static web
├── compose.yaml               # Docker Compose triển khai toàn bộ hệ thống
├── README.md                  # Hướng dẫn cài đặt và vận hành
├── documents/
│   └── SPEC.md                # Tài liệu đặc tả hệ thống hoàn chỉnh (SRS)
├── api/                       # Phân hệ Backend API (FastAPI)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── main.py            # Entrypoint FastAPI & Exception Handlers
│       ├── config.py          # Pydantic Settings
│       ├── middleware/        # X-Request-ID Middleware
│       ├── routes/            # /api/v1 (health, books, search, recommend, reader, qa)
│       ├── schemas/           # Pydantic schemas theo hợp đồng API
│       └── services/          # SnapshotService, AI loaders
├── pipeline/                  # Phân hệ Pipeline Dữ liệu (CLI ai-library)
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── ai_library/
│       └── cli.py             # CLI lệnh: import, build, validate, activate, rollback
├── web/                       # Phân hệ Frontend (React + TypeScript + Vite)
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx            # Client-side router & Navigation
│       ├── main.tsx
│       ├── components/        # Header, BookCard, Filters
│       ├── pages/             # Khám phá, Chi tiết, Gợi ý, Trình đọc
│       ├── services/          # apiClient, tabStorage (sessionStorage)
│       ├── styles/            # Thiết kế giao diện (index.css)
│       └── types/             # TypeScript API contracts
└── data/                      # Lưu trữ dữ liệu và kiểm soát snapshot
    ├── control/               # active.json, activation_request.json
    ├── snapshots/             # <snapshot_id>/{catalog.sqlite, books.faiss, chunks/}
    ├── raw/                   # Dữ liệu đợt nhập thô (catalog.jsonl, chapters.jsonl)
    ├── reports/               # Báo cáo kiểm tra và biên bản nhập
    └── taxonomy.json          # Danh mục mã thể loại và chủ đề đã duyệt
```

---

## 3. Tech Stack & Quyết định kỹ thuật

| Thành phần | Công nghệ / Thư viện đã chốt |
| :--- | :--- |
| **Frontend** | React 18, TypeScript, Vite, Lucide Icons, CSS Design System (Responsive 390px - 1280px) |
| **Backend API** | Python 3.11+, FastAPI, Pydantic v2, Uvicorn (1 worker) |
| **Vector Engine** | `faiss-cpu` (IndexFlatIP), PyTorch CPU, `multilingual-e5-small` |
| **Collation** | `PyICU` (locale `vi_VN`, strength `SECONDARY`) tạo `title_sort_key` |
| **LLM RAG** | Google Gemini Developer API (`gemini-3.5-flash-lite`, Free tier, Structured JSON) |
| **Reverse Proxy** | Caddy Server (Tự động cấp chứng chỉ HTTPS ACME, timeout 35s) |
| **Môi trường Cloud** | Google Compute Engine E2 custom (4 vCPU, 8 GiB RAM, Ubuntu 24.04 LTS) |

---

## 4. Hướng dẫn cài đặt và Chạy thử nghiệm

### 4.1. Chuẩn bị biến môi trường
Tạo tệp `.env` từ `.env.example`:
```bash
cp .env.example .env
# Chỉnh sửa GEMINI_API_KEY nếu cần kiểm thử tính năng RAG
```

### 4.2. Chạy toàn bộ hệ thống bằng Docker Compose (Khuyên dùng)
```bash
docker compose up --build
```
* **Frontend Web:** Truy cập tại `http://localhost` (hoặc domain cấu hình qua HTTPS)
* **Backend API Docs:** `http://localhost/docs`
* **Health Check:** `http://localhost/api/v1/health`

### 4.3. Chạy từng phân hệ ở môi trường Local Development

#### Backend API (FastAPI):
```bash
cd api
python -m venv .venv
# Trên Windows:
.venv\Scripts\activate
# Trên Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

#### Frontend (React + Vite):
```bash
cd web
npm install
npm run dev
# Truy cập tại http://localhost:3000 (đã cấu hình proxy /api/v1 sang localhost:8000)
```

---

## 5. Vận hành Pipeline dữ liệu (CLI `ai-library`)

Công cụ dòng lệnh `ai-library` dùng để chuẩn bị, kiểm tra và phát hành các snapshot dữ liệu bất biến:

```bash
# 1. Nhập và kiểm tra dữ liệu thô
docker compose run --rm pipeline import --batch /data/raw/batch_01

# 2. Xây dựng snapshot (tính vector embedding, tạo SQLite và FAISS)
docker compose run --rm pipeline build --snapshot snapshot-v1

# 3. Kiểm định chất lượng và schema của snapshot
docker compose run --rm pipeline validate --snapshot snapshot-v1

# 4. Kích hoạt snapshot làm bản phục vụ chính thức
docker compose run --rm pipeline activate --snapshot snapshot-v1

# 5. Liệt kê các snapshot hiện có
docker compose run --rm pipeline list-snapshots

# 6. Quay lại (Rollback) snapshot trước đó nếu có sự cố
docker compose run --rm pipeline rollback --snapshot snapshot-v0
```

---

## 6. Tiêu chí nghiệm thu & Ràng buộc an toàn
1. **Ranh giới tính năng:** Tuyệt đối không gọi LLM trong tính năng Tìm kiếm hoặc Gợi ý. LLM chỉ được gọi duy nhất trong RAG QA.
2. **Quyền riêng tư:** Khóa `GEMINI_API_KEY` chỉ lưu ở server, không bao giờ lộ vào bundle client.
3. **Graceful Degradation:** Khi hết hạn mức Gemini API hoặc lỗi kết nối, hệ thống trả về lỗi rõ ràng ở khung QA, trong khi danh mục, tìm kiếm và đọc sách vẫn hoạt động bình thường.

