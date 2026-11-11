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

Bố cục mã nguồn và tài liệu dưới đây bám các mục 2.1, 3.1, 9.3 và 14.6 của
[`documents/SPEC.md`](documents/SPEC.md), tài liệu gốc của toàn dự án.
Các module P4 và báo cáo được bổ sung theo commit riêng của từng task.

```text
UET.CS2046_6-G16-SmartLibAI/
├── .env.example               # Biến môi trường mẫu, không chứa secret thật
├── .gitignore
├── Caddyfile                  # HTTPS, static web và reverse proxy /api/v1
├── compose.yaml               # Web build, API một worker và pipeline theo lệnh
├── README.md
├── documents/
│   └── SPEC.md                # Đặc tả gốc, căn cứ thiết kế và nghiệm thu
├── specs/
│   └── p4/                    # Phân công, đặc tả task và nghiệm thu theo tuần
│       ├── README.md
│       ├── AGENTS.md
│       ├── templates/
│       └── week-01/ ... week-04/
├── api/                       # Backend FastAPI, chỉ đọc catalog/index/model
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── src/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── middleware/        # request_id và xử lý request chung
│   │   ├── routes/            # API theo hợp đồng mục 12
│   │   ├── schemas/           # Pydantic request/response
│   │   └── services/          # Nạp snapshot và các thành phần phục vụ
│   └── tests/
├── pipeline/                  # Chuẩn bị dữ liệu/index offline
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── requirements-faiss.txt # Môi trường kiểm chứng FAISS của P4
│   ├── ai_library/
│   │   ├── cli.py             # import/build/validate/activate/rollback/list/remove
│   │   ├── importer.py
│   │   ├── schema.py          # SQLite theo mô hình mục 9.3
│   │   ├── text_utils.py
│   │   ├── collation.py
│   │   ├── faiss_smoke.py     # C05: kiểm chứng FAISS bằng fixture
│   │   └── book_index.py      # C14: nhận vector P3, tạo index/mapping và loader
│   └── tests/
├── web/                       # React + TypeScript + Vite
│   ├── Dockerfile
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── components/
│   │   ├── pages/             # Khám phá, chi tiết, gợi ý và trình đọc
│   │   ├── services/          # API client, reader client, trạng thái tab
│   │   ├── fixtures/          # Dữ liệu mẫu, chỉ bật chủ động trong dev
│   │   ├── styles/
│   │   └── types/
│   └── tests/                 # Kiểm chứng browser của trình đọc
├── data/
│   ├── raw/                   # Batch nhập: catalog, chapters, taxonomy, registry
│   ├── reports/               # Báo cáo pipeline
│   ├── snapshots/             # Artefact phát hành bất biến
│   ├── control/               # Con trỏ active và điều phối vận hành
│   └── taxonomy.json          # Nguồn taxonomy biên tập hiện có
├── models/                    # Artefact encoder theo revision, giữ ngoài Git
└── openspec/                  # Quy trình và hồ sơ thực hiện, chỉ ở local
```

Layout của **snapshot hoàn chỉnh** phải theo mục 14.6:

```text
data/snapshots/<snapshot_id>/
├── catalog.sqlite
├── books.faiss
├── mapping.jsonl
├── chunks/<book_id>.faiss
└── manifest.json

data/control/
├── active.json
├── activation_request.json
├── activation_result.json
└── snapshots_registry.json

models/<revision>/...
```

Đây là cấu trúc artefact cần được pipeline tạo và kiểm định; các thư mục dữ liệu
trong Git chưa đồng nghĩa đã có snapshot hợp lệ. API mount snapshots/models
read-only và control read-write; pipeline nhập/build offline theo mục 14.6.
P3 sinh vector, P4 kiểm tra và xây FAISS/mapping; P1/P2 dùng chung index và vector.

Batch nhập chuẩn theo mục 3.1 chứa `catalog.jsonl`, `chapters.jsonl`,
`taxonomy.json`, `id_registry.json` và thư mục `raw/`. Importer hiện dùng taxonomy
chung hoặc đường dẫn `--taxonomy`; cách đóng băng taxonomy/registry cho từng batch
còn cần đồng bộ với hợp đồng chuẩn, không được coi công cụ hiện tại đã hoàn tất
yêu cầu này. Chi tiết hiện trạng importer tại mục 5.

Thành phần C14 gồm `books.faiss`, `mapping.jsonl`, `index_manifest.json`; đây là
bộ index để bàn giao và kiểm thử, còn snapshot hoàn chỉnh cần đầy đủ artefact
nêu trên. Tài liệu và bằng chứng P4 nằm tại [`specs/p4/`](specs/p4/README.md).
Hồ sơ `openspec/` được giữ local qua `.git/info/exclude`.

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

Để kiểm tra khung C04 bằng metadata C02 khi chưa có backend, từ thư mục `web` chạy `npm run dev:demo`. Kiểm tra build bằng `npm run build`. Hướng dẫn route Reader minh họa và vị trí bàn giao P1/P3/P4 nằm trong [`web/README.md`](web/README.md).

---

## 5. Vận hành Pipeline dữ liệu (CLI `ai-library`)

Công cụ dòng lệnh `ai-library` dùng để chuẩn bị, kiểm tra và phát hành các snapshot dữ liệu bất biến:

Catalog mẫu 20 sách được chia sẻ tại `data/raw/sample_batch/catalog.jsonl`.
Importer dùng duy nhất taxonomy chung `data/taxonomy.json` (có thể chỉ định bằng
`--taxonomy` hoặc biến `TAXONOMY_PATH`), không dùng taxonomy riêng trong batch.
Ở giai đoạn metadata, chạy từ thư mục gốc repository:

```bash
python -B -m pip show pydantic click
# Sau khi môi trường đã có dependencies trong pipeline/pyproject.toml:
cd pipeline
python -B -m ai_library.cli import --batch ../data/raw/sample_batch --metadata-only
# Hoặc dùng môi trường Docker đã chuẩn bị:
# docker compose run --rm pipeline import --batch /data/raw/sample_batch --metadata-only
```

`--metadata-only` bỏ qua các chương mẫu cũ; importer hiện chưa sử dụng
`id_registry.json` nên registry cũ không phải căn cứ ánh xạ cho catalog mới.
Không cần thêm chương hoặc toàn văn. Lệnh import chỉ validation/nạp trong bộ nhớ,
in số nhận/hợp lệ/cách ly và trả exit code 1 khi có lỗi hoặc catalog rỗng;
không ghi database hoặc snapshot. Các nguồn `pending` được nhận để phát triển
nội bộ, chưa đồng nghĩa được duyệt phát hành.
Các lệnh build/validate bên dưới hiện còn là khung, chưa tạo hoặc kiểm định
embedding/snapshot thực tế.

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

