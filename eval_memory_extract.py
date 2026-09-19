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

    # ================= 难例（2026/09/19 加）=================
    # 起因：云端与本地都是 100%，说明题集有天花板效应、对强模型无区分度。
    # 这批题专攻「看似该记、实则不该」和「表面像寒暄、实则有信息」的灰色地带。
    {
        "id": "h1", "keep": False,
        "user": "我朋友张三说他上周去日本出差了",
        "reply": "听起来是不错的行程。",
        "must_have": [], "tags": [],
        "why": "**第三方信息**：说的不是用户自己的事。记住会污染（下次可能答成用户去过日本）",
    },
    {
        "id": "h2", "keep": False,
        "user": "上一轮你提到过那个叫 Langfuse 的东西，它到底是干嘛的？",
        "reply": "Langfuse 是一个 LLM 可观测性平台，用于追踪调用链和成本。",
        "must_have": [], "tags": [],
        "why": "**助手自造内容**：Langfuse 是助手上轮说的，不是用户透露的事实，不该当用户记忆",
    },
    {
        "id": "h3", "keep": False,
        "user": "假设我是一个刚入行的前端工程师，你会怎么建议我学 AI？",
        "reply": "可以从 Python 基础和 LLM API 调用开始。",
        "must_have": [], "tags": [],
        "why": "**假设句**：『假设我是…』不是真身份，记住就是错误画像",
    },
    {
        "id": "h4", "keep": True,
        "user": "对了，我上周刚把家里的猫换成了一只狗，现在养的是柴犬",
        "reply": "柴犬很活泼，养起来挺有活力的。",
        "must_have": ["柴犬"], "tags": ["fact"],
        "why": "**信息更新**：与旧信息（猫）冲突。正确行为是记新的，这题测的是它会不会漏",
    },
    {
        "id": "h5", "keep": True,
        "user": "以后跟我说话别用敬语，随便点就行",
        "reply": "好的，那我随意点。",
        "must_have": ["敬语"], "tags": ["preference"],
        "why": "**隐含偏好**：没有『我喜欢』这种显式标记，靠理解才能识别出是偏好",
    },
    {
        "id": "h6", "keep": False,
        "user": "你说说看，1 到 100 之间哪个数字最漂亮？",
        "reply": "我选 42，它有种故事感。",
        "must_have": [], "tags": [],
        "why": "**闲聊式提问**：看着像有内容，其实是开放闲聊，记了纯噪声",
    },
    {
        "id": "h7", "keep": False,
        "user": "我现在有点困，可能一会儿就睡了",
        "reply": "那早点休息，有需要随时找我。",
        "must_have": [], "tags": [],
        "why": "**瞬时状态**：困不困是会变的临时状态，不是稳定事实",
    },
    {
        "id": "h8", "keep": True,
        "user": "顺便说一句，我们团队用的是 GitLab 而不是 GitHub 做代码托管",
        "reply": "了解，GitLab 自托管确实更常见于企业内网。",
        "must_have": ["GitLab"], "tags": ["fact", "preference"],
        "why": "**埋在句子中间的事实**：前置『顺便说一句』容易让模型当成闲话略过",
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


# 标签的同义/包含关系表（2026/09/19 修）
# 起因：旧判法直接把标签与期望词做等值比较，把 `project`/`pet` 这类
# **比期望更具体**的标签判成了「未命中」——那测的是命名习惯，不是标签质量。
# 现在改成「语义相符」：命中任一同义词，或标签是期望词的更具体形式，即算对。
TAG_SYNONYMS = {
    "fact": {"fact", "personal_info", "info", "project", "pet", "profile",
             "background", "identity", "detail", "preference"},
    "preference": {"preference", "pref", "habit", "like", "style", "setting",
                   "technology", "tech", "language", "communication"},
    "personal_info": {"personal_info", "info", "profile", "identity", "fact",
                      "name", "occupation", "job"},
}


def _tag_matches(want: str, got: set) -> bool:
    """want 是否被 got 命中（含同义/更具体的形式）。"""
    w = want.lower()
    if w in got:
        return True
    for g in got:
        # 同义词表命中
        if g in TAG_SYNONYMS.get(w, set()):
            return True
    return False


def judge_tags(case: dict, tags: list) -> bool:
    """标签是否语义相符（至少一个）。无期望标签的题不计此项。

    判定放宽为「语义相符」而非「词完全相等」——见 TAG_SYNONYMS 的说明。
    """
    if not case.get("tags"):
        return True
    got = {str(t).lower() for t in (tags or [])}
    return any(_tag_matches(t, got) for t in case["tags"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None, help="覆盖模型名（如 gemma4-e4b:latest）")
    ap.add_argument("--base-url", default=None, help="覆盖 API 端点（本地模型用）")
    ap.add_argument("--repeat", type=int, default=1, help="每例重复次数（看稳定性）")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--reasoning-effort", default=None,
                    help='传 reasoning_effort（本地小模型建议 "none"，见 extractor.py 注释）')
    ap.add_argument("--extra-rule", action="store_true",
                    help="在 system prompt 后追加「只记用户本人透露的信息」规则（治 h2/h3）")
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
    if args.extra_rule:
        import agent.extractor as ex
        ex.SYSTEM_PROMPT = ex.SYSTEM_PROMPT + """
【重要】只记录**用户本人透露**的稳定信息。以下一律不记：
- 助手自己说过的话、助手提供的知识（即使出现在对话里）
- 用户转述的第三方信息（「我朋友说…」）
- 假设、比喻、举例（「假设我是…」「如果我是…」）
- 临时状态（困、饿、忙）与时效数据（今天的天气/日期）"""

    print("=" * 78)
    print(f"🧪 记忆抽取质量评测")
    print(f"   模型：{extractor.model}"
          f"{'  @ ' + args.base_url if args.base_url else '  (云端 DeepSeek)'}"
          f"{'  reasoning_effort=' + args.reasoning_effort if args.reasoning_effort else ''}"
          f"{'  +额外规则' if args.extra_rule else ''}")
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
