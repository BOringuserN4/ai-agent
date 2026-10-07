#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doc_freshness_check.py — 文档新鲜度巡检（确定性收集，不做判断）

为什么需要它（见 docs/00-索引/issue-log-review-2026-10-07.md）：
  文档里最易腐坏的不是"数字"，而是「**现状**」这类**对当下的断言** ——
  升级后它静默变假，且与真话无法区分。2026/10/07 一次复核就抓到 6 处。

本脚本**只做确定性收集**（grep 高风险措辞 + 少量代码交叉核对），
**判断"是否真过期"交给调用方（agent/人）** —— 因为多数命中是合法语境。

用法：
    python3 scripts/doc_freshness_check.py            # 打印 Markdown 报告
    python3 scripts/doc_freshness_check.py --quiet    # 只打印摘要
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 高风险措辞：对"当下"的断言，升级后会静默变假
RISKY = ["（现状）", "(现状)", "现状是", "尚未", "真欠", "⬜", "缺：", "未做", "没有实现"]

# 扫描范围（相对 ROOT）
SCAN_DIRS = ["docs", "agent", "scripts"]
SCAN_FILES = ["README.md", "main.py"]

# 排除：规则自身 / 复核报告的措辞范例（避免自我指涉的噪声）
EXCLUDE_PATTERNS = [
    r"docs/00-索引/issue-log\.md",          # #38/#39 描述规则本身
    r"docs/00-索引/issue-log-review-.*\.md",
]


def iter_targets():
    seen = set()
    for d in SCAN_DIRS:
        for base, dirs, files in os.walk(os.path.join(ROOT, d)):
            dirs[:] = [x for x in dirs if x not in ("__pycache__", ".git", "node_modules")]
            for f in files:
                if f.endswith((".md", ".py", ".js")):
                    yield os.path.join(base, f)
    for f in SCAN_FILES:
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            yield p


def rel(p):
    return os.path.relpath(p, ROOT)


def excluded(p):
    r = rel(p)
    return any(re.search(pat, r) for pat in EXCLUDE_PATTERNS)


def scan_candidates():
    hits = []
    for p in iter_targets():
        if excluded(p):          # 排除规则自身 / 复核报告的措辞范例（避免自我指涉噪声）
            continue
        try:
            lines = open(p, encoding="utf-8").read().splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            for mark in RISKY:
                if mark in line:
                    hits.append({"file": rel(p), "line": i, "mark": mark,
                                 "text": line.strip()[:160]})
                    break
    return hits


# ---------------- 确定性交叉核对（真事实 vs 文档声称）----------------
def cross_checks():
    checks = []

    # 1) README / memory 头注释里的 embedding 模型 vs 代码默认值
    model = None
    try:
        src = open(os.path.join(ROOT, "agent", "embedding_backends.py"), encoding="utf-8").read()
        m = re.search(r'DEFAULT_MODEL\s*=\s*"([^"]+)"', src)
        if m:
            model = m.group(1)
    except Exception:
        pass
    if model:
        for f in ["README.md"]:
            try:
                t = open(os.path.join(ROOT, f), encoding="utf-8").read()
            except Exception:
                continue
            claimed = set(re.findall(r"text-embedding-v\d+", t))
            wrong = {c for c in claimed if c != model and c != ""}
            # 仅当 README 把非默认模型描述为"当前使用"时才可疑
            if wrong and model not in claimed:
                checks.append({
                    "name": "embedding 模型一致性",
                    "ok": False,
                    "detail": f"代码默认 {model}，但 {f} 提到 {sorted(wrong)}（未见 {model}）",
                })
            else:
                checks.append({"name": "embedding 模型一致性", "ok": True,
                               "detail": f"代码默认 {model}；{f} 声称 {sorted(claimed) or '（未提）'}"})

    # 2) 关键词计数（趋势用）
    try:
        n_bak = len(open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read().splitlines())
        checks.append({"name": ".gitignore 可读", "ok": True, "detail": f"{n_bak} 行"})
    except Exception as e:
        checks.append({"name": ".gitignore 可读", "ok": False, "detail": str(e)})

    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    hits = scan_candidates()
    checks = cross_checks()

    by_file = {}
    for h in hits:
        by_file.setdefault(h["file"], []).append(h)

    print("# 文档新鲜度巡检报告")
    print()
    print(f"- 扫描范围：{', '.join(SCAN_DIRS + SCAN_FILES)}")
    print(f"- 高风险措辞命中：**{len(hits)} 条**，涉及 **{len(by_file)} 个文件**")
    print()
    print("## 确定性交叉核对")
    print()
    print("| 检查 | 结果 | 详情 |")
    print("|---|---|---|")
    for c in checks:
        print(f"| {c['name']} | {'✅' if c['ok'] else '❌'} | {c['detail']} |")
    print()

    if not args.quiet:
        print("## 候选清单（需人工/agent 判断，多数为合法语境）")
        print()
        for f in sorted(by_file, key=lambda x: -len(by_file[x])):
            print(f"### `{f}`（{len(by_file[f])} 条）")
            for h in by_file[f][:30]:
                print(f"- L{h['line']} 〔{h['mark']}〕 {h['text']}")
            print()

    print("---")
    print("> 判定规则：优先复核「现状 / 没有 / 缺 / 尚未 / ⬜」——它们是对当下的断言，")
    print("> 升级后会静默变假。数字（写在实验语境里）通常不需复核。")
    print("> 详见 `docs/00-索引/issue-log.md` #38/#39。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
