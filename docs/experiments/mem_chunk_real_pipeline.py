# -*- coding: utf-8 -*-
"""真实管线复现：两轮对话 → 抽取器 → 存储 → 查询（2026/10/03）

前面用的是手写的"理想记忆"。本脚本走真实路径：
  用 MemoryExtractor 从真实两轮对话抽取，看真实产出什么记忆、能否召回。
特别关注：第二轮「它叫毛毛」这种**带代词**的短句会不会被丢弃/变形。
"""
import os, sys, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

from agent.memory import MemoryStore, MIN_SCORE
from agent.extractor import MemoryExtractor, build_embed_text

TMP = os.path.join(ROOT, "tmp-artifacts", "chroma_memchunk_real")
shutil.rmtree(TMP, ignore_errors=True)

turns = [
    ("我养了一只英短猫", "英短是很可爱的品种，性格温顺。"),
    ("它叫毛毛", "好的，毛毛这个名字很好听！"),
]

ex = MemoryExtractor()
mem = MemoryStore(top_k=8, chroma_dir=TMP)
print("=== 真实抽取结果 ===")
for i, (u, a) in enumerate(turns, 1):
    r = ex.extract(u, a)
    print(f"第{i}轮 输入={u!r}")
    print(f"      keep={r.get('keep')}  text={r.get('text')!r}  tags={r.get('tags')}")
    print(f"      questions={r.get('questions')}")
    if r.get("keep") and r.get("text"):
        tags = r.get("tags", [])
        stored = f"[{','.join(tags)}] {r['text']}" if tags else r["text"]
        embed = build_embed_text(r["text"], r.get("questions"))
        mem.add(stored, meta={"tags": tags}, embed_text=f"[{','.join(tags)}] {embed}" if tags else embed)

print(f"\n库中共 {mem.count()} 条记忆")
for t in mem.all_texts():
    print("  -", t)

print(f"\n=== 查询（阈值 {MIN_SCORE}）===")
for q in ["我那只英短叫什么", "我家猫叫什么名字", "我养的猫叫啥", "毛毛是谁的猫"]:
    hits = mem.search(q)
    print(f"\n查询：{q}")
    for h in hits:
        print(f"    {h['score']:.4f}  {h['text']}")
