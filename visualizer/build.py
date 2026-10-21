#!/usr/bin/env python3
"""把 trace.jsonl / trace_full.jsonl 注入 template-seq.html，生成单文件回放页。"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name: str) -> list[dict]:
    path = ROOT / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    traces = {
        "dev": load("trace_dev.jsonl"),
        "full": load("trace_full.jsonl"),
        "minimal": load("trace.jsonl"),
    }
    payload = json.dumps(traces, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")

    html = (ROOT / "template-seq.html").read_text(encoding="utf-8")
    marker = "/*__TRACES_JSON__*/{}"
    if marker not in html:
        raise SystemExit("template 缺少 marker: " + marker)
    html = html.replace(marker, payload)
    out = ROOT / "index.html"
    out.write_text(html, encoding="utf-8")
    print("traces:", {k: len(v) for k, v in traces.items()})
    print(f"wrote: {out} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
