# -*- coding: utf-8 -*-
"""
eval_memory_extract.py — 记忆抽取质量评测（2026/09/19）

背景：`agent/extractor.py` 每轮对话后判断「这条值不值得长期记住」，
      现在走云端 DeepSeek（deepseek-flash）。想评估本地小模型能否替代。

**但换之前必须先有一把尺子** —— 否则无法判断「换了是好是坏」。
本脚本就是那把尺子：同一套用例，谁跑都是同样 20 题、同样判分。

=== 评测的三个维度（分开算，不揉成一个分） ===

1. **keep 判断**（最重要）
   该记的记没记住？不该记的有没有污染记忆库？
   - 漏记（该记没记）：损失一条信息
   - 误记（不该记却记了）：**污染记忆库，更严重**（会长期影响检索）
   所以两个方向分开统计，不只看准确率。

2. **text 质量**（概括得准不准）
   抽取出来的那句话，有没有丢掉关键信息？
   用**关键词覆盖**判定（确定性，不靠 LLM 打分）。

3. **tags 质量**
   类别标签对不对。

=== 判分原则 ===

**能测量的绝不让 LLM 判**（本项目一贯原则）：
  - keep 是否相等 → 直接比布尔值
  - text 是否含关键信息 → 关键词包含判定
  - tags 是否对 → 集合比较
不用 LLM-as-judge，因为这三个都能客观测，引入 judge 反而增加噪声源。

用法：
    .venv/bin/python eval_memory_extract.py                 # 当前配置（默认云端）
    .venv/bin/python eval_memory_extract.py --model X       # 指定模型
    .venv/bin/python eval_memory_extract.py --repeat 3      # 每例跑 3 次看稳定性
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


# ============================================================
# 测试用例：(用户说, 助手答) → 期望
#
#   keep:        是否应该长期记住
#   must_have:   keep=True 时，概括文本里**必须**出现的关键词（至少命中一个）
#   must_not:    keep=True 时，概括文本里**不该**出现的词（防跑偏）
#   tags:        期望的标签（至少命中一个）
#   why:         出这道题的理由（给人看，方便日后 review 题集质量）
#
# 设计原则（照着 golden_set.py 的规矩）：
#   1. 宁精勿滥；2. 不写死唯一答案，只写要点；3. 边界/异常必须存在。
#
# ⚠️ 已知局限（2026/09/19 实测后补记）：
#   云端 deepseek-flash 在本套 12 题上**满分**（keep 12/12、概括 5/5、标签 5/5）。
#   这意味着**题集对强模型没有区分度（天花板效应）**。
#   它的正确用途是当「**下限门槛**」：本地模型若低于满分，说明确实更差；
#   若也是满分，则说明本套题太容易，**不能据此断言两者等价**——
#   要区分需加更难的反例（如「用户提到的第三方信息」「助手自己编的例子」）。
# ============================================================

CASES = [
    # ---------- 该记：用户偏好 / 个人信息 ----------
    {
        "id": "k1", "keep": True,
        "user": "我叫小王，是一名测试开发工程师",
        "reply": "你好小王！测试开发工程师是个很有意思的岗位。",
        "must_have": ["小王", "测试"], "tags": ["preference", "fact"],
        "why": "用户自报姓名+职业，最常见的「该记」",
    },
    {
        "id": "k2", "keep": True,
        "user": "我平时更喜欢用 Python 而不是 Java",
        "reply": "好的，Python 在数据处理上确实更顺手。",
        "must_have": ["Python"], "tags": ["preference"],
        "why": "技术偏好，跨会话有用",
    },
    {
        "id": "k3", "keep": True,
        "user": "我正在做一个叫 ai-agent 的教学项目，现在在学多 Agent 编排",
        "reply": "这个方向很好，多 Agent 编排确实是进阶重点。",
        "must_have": ["ai-agent", "多 Agent", "编排"], "tags": ["fact"],
        "why": "项目阶段，跨会话强相关",
    },
    {
        "id": "k4", "keep": True,
        "user": "我养了一只猫叫豆豆",
        "reply": "豆豆这名字真可爱！",
        "must_have": ["豆豆"], "tags": ["fact"],
        "why": "个人事实",
    },

    # ---------- 不该记：寒暄 / 客套 ----------
    {
        "id": "n1", "keep": False,
        "user": "你好",
        "reply": "你好！有什么可以帮你的吗？",
        "must_have": [], "tags": [],
        "why": "纯寒暄，最典型的「不该记」（题集里绝不能只有该记的）",
    },
    {
        "id": "n2", "keep": False,
        "user": "谢谢你",
        "reply": "不客气！",
        "must_have": [], "tags": [],
        "why": "客套话",
    },
    {
        "id": "n3", "keep": False,
        "user": "嗯嗯",
        "reply": "嗯，还有什么想问的随时说。",
        "must_have": [], "tags": [],
        "why": "模糊应答，无信息量",
    },

    # ---------- 不该记：一次性计算 / 查询 ----------
    {
        "id": "n4", "keep": False,
        "user": "帮我算 123 * 456",
        "reply": "123 * 456 = 56088",
        "must_have": [], "tags": [],
        "why": "一次性计算，记了就是污染",
    },
    {
        "id": "n5", "keep": False,
        "user": "上海现在天气怎么样？",
        "reply": "上海当前：阴天，25.6°C，风速 8.6 km/h。",
        "must_have": [], "tags": [],
        "why": "**边界题**：含具体数值，容易被误判为「事实」而记住——但它是时效性数据",
    },
    {
        "id": "n6", "keep": False,
        "user": "什么是向量数据库？",
        "reply": "向量数据库是专门存储和检索高维向量的数据库，支持语义搜索。",
        "must_have": [], "tags": [],
        "why": "**边界题**：通用知识问答，不是「关于用户的事实」——最容易被误记",
    },

    # ---------- 边界：混合内容（既有寒暄又有信息）----------
    {
        "id": "b1", "keep": True,
        "user": "早上好啊，顺便说一下我以后都用中文跟你交流",
        "reply": "早上好！好的，之后都用中文。",
        "must_have": ["中文"], "tags": ["preference"],
        "why": "**混合题**：寒暄+偏好混在一起，正确行为是「留住偏好、丢掉寒暄」",
    },
    {
        "id": "b2", "keep": False,
        "user": "今天几号？",
        "reply": "今天是 2026-09-19。",
        "must_have": [], "tags": [],
        "why": "**边界题**：时间类查询，时效数据不该进长期记忆",
    },
]


# ============================================================
# 判分（全部确定性，不用 LLM）
# ============================================================

def judge_keep(expected: bool, got: bool) -> str:
    """keep 判断结果分类。区分「漏记」和「误记」——两者严重性不同。"""
    if expected and got:
        return "hit"          # 正确记录
    if not expected and not got:
        return "correct_skip"  # 正确跳过
    if expected and not got:
        return "miss"          # 漏记：丢信息
    return "pollute"           # 误记：污染记忆库（更严重）


def judge_text(case: dict, extracted: str) -> bool:
    """概括文本是否保住了关键信息（关键词覆盖）。keep=False 的题不计此项。"""
    if not case.get("must_have"):
        return True
    text = extracted or ""
    return any(kw.lower() in text.lower() for kw in case["must_have"])


def judge_tags(case: dict, tags: list) -> bool:
    """标签是否命中（至少一个）。无期望标签的题不计此项。"""
    if not case.get("tags"):
        return True
    got = {str(t).lower() for t in (tags or [])}
    return any(t.lower() in got for t in case["tags"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None, help="覆盖模型名（如 gemma4-e4b:latest）")
    ap.add_argument("--base-url", default=None, help="覆盖 API 端点（本地模型用）")
    ap.add_argument("--repeat", type=int, default=1, help="每例重复次数（看稳定性）")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--reasoning-effort", default=None,
                    help='传 reasoning_effort（本地小模型建议 "none"，见 extractor.py 注释）')
    ap.add_argument("--save", default=None,
                    help="把结果存成 JSON（用于跨模型对比，如 --save baseline_cloud.json）")
    args = ap.parse_args()

    from agent.extractor import MemoryExtractor

    extractor = MemoryExtractor()
    if args.model:
        extractor.model = args.model
    if args.base_url:
        # 本地模型走 OpenAI 兼容端点
        from openai import OpenAI
        extractor.client = OpenAI(api_key="***", base_url=args.base_url)
        extractor._ensure_client = lambda: extractor.client
    if args.reasoning_effort:
        extractor.reasoning_effort = args.reasoning_effort

    print("=" * 78)
    print(f"🧪 记忆抽取质量评测")
    print(f"   模型：{extractor.model}"
          f"{'  @ ' + args.base_url if args.base_url else '  (云端 DeepSeek)'}"
          f"{'  reasoning_effort=' + args.reasoning_effort if args.reasoning_effort else ''}")
    print(f"   用例：{len(CASES)} 条｜每例跑 {args.repeat} 次")
    print("=" * 78)

    stats = {"hit": 0, "correct_skip": 0, "miss": 0, "pollute": 0}
    text_ok = text_total = 0
    tag_ok = tag_total = 0
    keep_stable = 0
    latencies = []
    rows = []

    for case in CASES:
        keeps, texts, tagsets = [], [], []
        for _ in range(args.repeat):
            t0 = time.time()
            r = extractor.extract(case["user"], case["reply"])
            latencies.append(time.time() - t0)
            keeps.append(bool(r.get("keep")))
            texts.append(r.get("text", ""))
            tagsets.append(r.get("tags", []))

        got_keep = keeps[0]
        result = judge_keep(case["keep"], got_keep)
        stats[result] += 1

        if len(set(keeps)) == 1:
            keep_stable += 1

        t_ok = judge_text(case, texts[0]) if got_keep else True
        g_ok = judge_tags(case, tagsets[0]) if got_keep else True
        if case["keep"] and got_keep:
            text_total += 1
            tag_total += 1
            text_ok += t_ok
            tag_ok += g_ok

        rows.append((case, got_keep, result, texts[0], tagsets[0], t_ok, g_ok))

    # ---- 逐条 ----
    print(f"\n{'ID':<5}{'期望':<7}{'实际':<7}{'判定':<14}{'概括':<44}")
    print("-" * 78)
    icon = {"hit": "✅ 记", "correct_skip": "✅ 跳过",
            "miss": "❌ 漏记", "pollute": "⚠️ 误记(污染)"}
    for case, got, result, text, tags, t_ok, g_ok in rows:
        mark = icon.get(result, "?")
        extra = ""
        if case["keep"] and got:
            extra = f"{'T' if t_ok else 't'}{'G' if g_ok else 'g'}"
        print(f"{case['id']:<5}{str(case['keep']):<7}{str(got):<7}{mark:<14}"
              f"{(text or '')[:40]:<44}")
        if args.verbose and case.get("why"):
            print(f"      ↳ {case['why']}")

    # ---- 汇总 ----
    n = len(CASES)
    should_keep = sum(1 for c in CASES if c["keep"])
    should_skip = n - should_keep

    print("\n" + "=" * 78)
    print("📊 结果")
    print("=" * 78)
    print(f"── keep 判断（最重要）──")
    print(f"   该记的 {should_keep} 条 → 正确记下 {stats['hit']}，"
          f"**漏记 {stats['miss']}**（漏记=丢信息）")
    print(f"   该跳的 {should_skip} 条 → 正确跳过 {stats['correct_skip']}，"
          f"**误记 {stats['pollute']}**（误记=污染记忆库，更严重）")
    keep_acc = (stats["hit"] + stats["correct_skip"]) / n
    print(f"   keep 准确率：{keep_acc:.0%}  ({stats['hit'] + stats['correct_skip']}/{n})")
    if args.repeat > 1:
        print(f"   稳定性：{keep_stable}/{n} 条在 {args.repeat} 次里判断一致")

    print(f"\n── 概括质量（仅统计「该记且记了」的 {text_total} 条）──")
    print(f"   关键词覆盖：{text_ok}/{text_total}"
          f"{f' = {text_ok/text_total:.0%}' if text_total else ''}")

    print(f"\n── 标签质量 ──")
    print(f"   标签命中：{tag_ok}/{tag_total}"
          f"{f' = {tag_ok/tag_total:.0%}' if tag_total else ''}")

    if latencies:
        lat = sorted(latencies)
        print(f"\n── 延迟（{len(latencies)} 次调用）──")
        print(f"   中位 {lat[len(lat)//2]*1000:.0f}ms｜"
              f"P90 {lat[int(len(lat)*0.9)]*1000:.0f}ms｜"
              f"最慢 {lat[-1]*1000:.0f}ms")

    # ---- 落盘（可选）----
    if args.save:
        import json
        payload = {
            "model": extractor.model,
            "base_url": args.base_url or "cloud(deepseek)",
            "cases": len(CASES), "repeat": args.repeat,
            "keep_accuracy": keep_acc,
            "hit": stats["hit"], "correct_skip": stats["correct_skip"],
            "miss": stats["miss"], "pollute": stats["pollute"],
            "text_coverage": f"{text_ok}/{text_total}",
            "tag_hit": f"{tag_ok}/{tag_total}",
            "latency_median_ms": round(lat[len(lat)//2]*1000) if latencies else None,
            "per_case": [
                {"id": c["id"], "expect_keep": c["keep"], "got_keep": g,
                 "verdict": v, "text": t, "tags": tg}
                for c, g, v, t, tg, _, _ in rows
            ],
        }
        with open(args.save, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\n💾 已存至 {args.save}")

    print("\n怎么读这张表：")
    print("  · **误记（污染）比漏记更该盯**——漏记只是少条信息，"
          "误记会长期干扰检索")
    print("  · n5/n6 是边界题（时效数据、通用知识），"
          "最容易被误判成「事实」而记住")
    print("  · 概括质量看 T 列（关键词覆盖），t 表示丢了关键信息")
    print("  · 换本地模型时，比较的是**同一套题**的分数，不是绝对值好不好看")

    return 0


if __name__ == "__main__":
    sys.exit(main())
