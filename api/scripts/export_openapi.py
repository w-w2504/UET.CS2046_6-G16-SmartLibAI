"""Xuất OpenAPI từ FastAPI, không yêu cầu snapshot hoặc model."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from src.main import app

ROOT = Path(__file__).resolve().parents[2]


def contract_document():
    document = deepcopy(app.openapi())
    fixtures = ROOT / "contracts/fixtures"
    scenarios = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    for scenario in scenarios:
        operation = document["paths"].get(scenario["path"], {}).get(scenario["method"].lower(), {})
        response = operation.get("responses", {}).get(str(scenario["status"]), {})
        media = response.get("content", {}).get("application/json")
        if media is not None:
            payload = json.loads((fixtures / scenario["response"]).read_text(encoding="utf-8"))
            media.setdefault("examples", {})[scenario["scenario_id"]] = {
                "summary": "Mô phỏng nội bộ: " + scenario["scenario_id"], "value": payload,
            }
    return document


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = ROOT / "contracts/openapi.json"
    content = json.dumps(contract_document(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.check:
        if target.read_text(encoding="utf-8") != content:
            parser.exit(1, "OpenAPI đã thay đổi. Hãy xuất lại artifact.\n")
    else:
        target.write_text(content, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
