# -*- coding: utf-8 -*-
"""
agent/golden_set.py — 评测数据集（Golden Set，2026/09/10）

为什么需要「金标准数据集」？
  - 没有固定题集，就没法比较「改前 vs 改后」谁更好 —— 评测要可复现。
  - 同一批题、同样的期望，跑 N 次看分数波动，才知道改动是真提升还是噪声。
  - 题集要覆盖：正常 / 边界 / 异常 三类（对应大纲 9.3 避坑清单）。

一条评测样例（case）的字段：
  - id:        唯一标识，报告里用来定位
  - input:     发给 Agent 的用户输入
  - category:  math / weather / general / edge —— 分类统计用
  - expected:  参考答案（给 LLM-as-judge 当「标准答案」比对，写要点而非唯一措辞）
  - checks:    关键要点列表（judge 逐条核对，避免只看表面像不像）
  - tags:      附加标签（正常 / 边界 / 异常），便于过滤与统计

设计原则（重要，别只抄）：
  1. 题量宁精勿滥：12 条覆盖四类，够跑通闭环；要扩再按同一模板加。
  2. expected 不写死唯一答案，而是写「要点」—— 自然语言表述千变万化，
     评测必须容忍表达差异，只认事实与要点是否到位。
  3. 边界/异常题必须存在：只测「你好我好」的题，评测等于安慰剂。
"""

# 评测数据集：12 条，覆盖 math / weather / general / edge 四类
GOLDEN_SET = [
    # ---------- math：正常计算 ----------
    {
        "id": "m1",
        "input": "帮我算 123 * 456",
        "category": "math",
        "expected": "56088",
        "checks": ["结果为 56088", "确实调用了计算器而非心算"],
        "tags": ["正常"],
    },
    {
        "id": "m2",
        "input": "计算 (12 + 8) * 5 - 30 / 6 等于多少？",
        "category": "math",
        "expected": "95",
        "checks": ["结果为 95", "运算顺序正确"],
        "tags": ["正常"],
    },
    {
        "id": "m3",
        "input": "一个班级 45 人，每人交 12.5 元班费，一共多少钱？",
        "category": "math",
        "expected": "562.5 元",
        "checks": ["结果为 562.5", "带上了单位（元）"],
        "tags": ["正常", "应用题"],
    },
    # ---------- weather：正常查询 ----------
    {
        "id": "w1",
        "input": "上海现在天气怎么样？",
        "category": "weather",
        "expected": "包含上海当前天气（温度，可含天气描述）",
        "checks": ["给出了温度数值", "没有编造，来自工具返回"],
        "tags": ["正常"],
    },
    {
        "id": "w2",
        "input": "北京今天热不热？",
        "category": "weather",
        "expected": "包含北京当前温度，并对冷热给出判断",
        "checks": ["给出了北京温度", "对『热不热』做了回应"],
        "tags": ["正常", "隐含意图"],
    },
    # ---------- general：通用问答 ----------
    {
        "id": "g1",
        "input": "用一句话解释什么是大语言模型。",
        "category": "general",
        "expected": "一句话说明大语言模型是基于大规模文本训练的、能预测/生成文本的模型",
        "checks": ["解释准确", "控制在一句话左右"],
        "tags": ["正常"],
    },
    {
        "id": "g2",
        "input": "你好，随便聊聊，你都能做什么？",
        "category": "general",
        "expected": "友好回应，并说明自己能做的事",
        "checks": ["语气友好", "说明了能力范围"],
        "tags": ["正常"],
    },
    {
        "id": "g3",
        "input": "把这句话翻译成英文：今天天气很好。",
        "category": "general",
        "expected": "The weather is nice today.",
        "checks": ["翻译基本准确", "是英文"],
        "tags": ["正常"],
    },
    # ---------- edge：异常 / 边界 ----------
    {
        "id": "e1",
        "input": "帮我算一下 100 / 0",
        "category": "edge",
        "expected": "说明除数不能为 0 / 该运算无意义，而不是给出错误数字",
        "checks": ["识别出除以零不合法", "没有编造结果"],
        "tags": ["异常"],
    },
    {
        "id": "e2",
        "input": "拉萨现在天气怎么样？",
        "category": "edge",
        "expected": "说明当前演示环境不支持该城市（内置仅北上广深杭蓉）",
        "checks": ["明确告知不支持", "没有编造天气数据"],
        "tags": ["异常"],
    },
    {
        "id": "e3",
        "input": "帮我算 3 + 5，另外顺便告诉我巴黎今天天气。",
        "category": "edge",
        "expected": "至少正确算出 3+5=8；巴黎天气若超出能力应如实说明",
        "checks": ["正确算出 8", "对超纲部分不编造"],
        "tags": ["边界", "混合意图"],
    },
    {
        "id": "e4",
        "input": "现在几点了？（北京时间）",
        "category": "edge",
        "expected": "给出北京时间（Asia/Shanghai）的当前时刻",
        "checks": ["调用了时间工具", "时区为 Asia/Shanghai"],
        "tags": ["边界"],
    },
    {
        "id": "e5",
        "input": "上海和北京比，哪个更宜居？",
        "category": "edge",
        "expected": (
            "不能只凭天气就下『哪更宜居』的结论。合格回答应满足其一："
            "(a) 给出两地天气数据，并说明宜居还需其它维度（房价/空气/医疗等）；"
            "(b) 说明该问题超出工具能力、无法判定。"
        ),
        "checks": [
            "没有编造宜居结论",
            "如给出数据则上海、北京两地都覆盖",
            "说明了局限或超出能力",
        ],
        "tags": ["边界", "能力边界", "多实体"],
    },
    {
        "id": "e6",
        "input": "帮我算 (88+12)*3，再查一下广州现在天气，两个都要告诉我。",
        "category": "edge",
        "expected": "必须同时给出【计算结果 300】和【广州当前天气（含温度）】。漏掉任一半即不合格。",
        "checks": [
            "算出 (88+12)*3 = 300",
            "给出广州当前天气（含温度数值）",
            "两部分都回答，没有遗漏任何一半",
        ],
        "must_have": ["计算结果 300", "广州当前天气"],
        "tags": ["边界", "跨域", "需两个专家"],
    },
]


def get_case(case_id: str):
    """按 id 取一条样例，找不到返回 None。"""
    for c in GOLDEN_SET:
        if c["id"] == case_id:
            return c
    return None


def categorize():
    """返回 {category: [case, ...]}，便于按类别统计。"""
    out = {}
    for c in GOLDEN_SET:
        out.setdefault(c["category"], []).append(c)
    return out


if __name__ == "__main__":
    # 自检：打印题集概览（写完先跑这个，确认结构没写错）
    cats = categorize()
    print(f"📚 Golden Set 共 {len(GOLDEN_SET)} 条")
    for name, cases in cats.items():
        print(f"  - {name}: {len(cases)} 条 -> {[c['id'] for c in cases]}")
