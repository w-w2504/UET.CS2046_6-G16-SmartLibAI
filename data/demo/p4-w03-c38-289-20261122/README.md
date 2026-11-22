# C38 — Bộ FAISS ứng viên289 sách

Nhận bundle P3 a0666cc, không encode lại sách. Index mới có289vector384float32/L2; nguồn catalog Search289/taxonomy/bundle nằm trong data/raw/p3_v4/search và data/demo/smartlibai-fasttrack/smartlibai-demo-v4. Source manifest trong index truy vết đúng hash/config.

289/289roundtrip/selfquery và3queryViệt khớp toàn289vị trí với NumPy; scores giống indexP3. Lõi C13 kiểm1/2/3seed, seed/ẩn/workdedup/fulltextempty. API P3 kiểm289details/5excluded404 và17query/filter thật đạt sau warmup.142test sau merge đạt; bộ150 cũ không đổi và vẫn nạp được.

Snapshot Search mới p4-c38-demo289-20261122 có SQLite/FAISS/mapping,0quarantined,289/289top5 thamchiếu. Đây là ứng viên classroom: giữ nguồn pending và ngưỡng0.75 minh họa, không phải publicvalidated/AIquality đãđo. P1/P2 dùng đúng snapshot và sourcebundle, không trộn với Reader2 hoặc bộ150.

P1 chạy Search: PYTHONPATH=api;pipeline, SMARTLIBAI_DEMO_SNAPSHOT trỏ tới thư mục snapshot/p4-c38-demo289-20261122 trong bộ này, MODEL_ROOT trỏ tới thư mục chứa hub có E5 đúngrevision, offline. Chạy Uvicorn127.0.0.1:8000 và Vite từweb. P2 nạp index bằng load_book_index(..., classroom_demo=True); get_vector/search và NumpyBookScorer dùng cùng metadata/bundle.manifest hash. Không phải chạy lại encoder sách.
