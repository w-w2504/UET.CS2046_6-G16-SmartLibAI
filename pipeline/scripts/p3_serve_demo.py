"""Warm the pinned query encoder before opening the demo HTTP listener."""

import argparse
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / path) for path in ('api', 'pipeline')]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    import uvicorn
    from ai_library.e5_encoder import embedding_config
    from src.services.search import search_service

    search_service.get_encoder(embedding_config()).encode_queries(['thư viện'])
    print('E5 warmed; starting API in the same process. No book vectors generated.', flush=True)
    uvicorn.run('src.main:app', host='127.0.0.1', port=args.port)
