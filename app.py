# -*- coding: utf-8 -*-
"""
app.py — 可视化朝堂 Web 界面后端（Flask）

启动方式：
    python3 app.py
然后浏览器打开 http://127.0.0.1:5000

提供两个 API：
  GET  /api/experts -> 返回专家（大臣）档案清单
  POST /api/chat    -> 接收皇帝（用户）问话，走 MultiAgent 流程，返回结构化结果
"""
from flask import Flask, jsonify, request, render_template
from agent.multi_agent import MultiAgent

app = Flask(__name__)
ma = MultiAgent()

# 专家（大臣）档案：仅供前端渲染大臣的身份/形象
EXPERT_PROFILES = {
    "math": {
        "name": "计算大臣",
        "title": "工部 · 稽算司",
        "emoji": "🧮",
        "desc": "掌天下数算、策试、赋税稽核，凡涉及数目、运算者皆归其辖。",
        "color": "#c8a95a",
    },
    "weather": {
        "name": "钦天监正",
        "title": "钦天监 · 观象台",
        "emoji": "☁️",
        "desc": "职司观星象、候天气、司辰漏，凡风雨阴晴、四时气候皆问之。",
        "color": "#5a9bc8",
    },
    "general": {
        "name": "大学士",
        "title": "文渊阁 · 起居注",
        "emoji": "📜",
        "desc": "博古通今，应答杂问、掌故、见闻，为圣上备顾问。",
        "color": "#8a7bc8",
    },
}


@app.route("/")
def index():
    # 把专家档案传给模板，默认首页渲染
    return render_template("index.html", experts=EXPERT_PROFILES)


@app.route("/api/experts")
def experts():
    return jsonify(EXPERT_PROFILES)


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    user_input = (data.get("message") or "").strip()
    if not user_input:
        return jsonify({"error": "no message"}), 400
    try:
        result = ma.run_detailed(user_input)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # debug=True 方便开发时看到报错，生产请关掉
    app.run(host="127.0.0.1", port=5000, debug=True)
