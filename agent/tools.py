# -*- coding: utf-8 -*-
"""
agent/tools.py — 工具大本营

这里集中存放 Agent 能调用的「真实工具」。
每个工具 = 一个 Python 函数。我们可以把整个配置文件当作「工具注册表」。

约定：
- 每个函数标注名字和说明（给模型看的「工具说明书」）。
- get_tools_spec() 返回 OpenAI Function Calling 格式的声明清单。
- get_tool_registry() 返回「工具名 -> 函数」的映射，供 Agent 调度执行。
"""
import datetime
import urllib.request
import urllib.parse
import json


# ============================================================
# 真实工具函数体（这是 Agent 的「手」，真正执行的地方）
# ============================================================

def get_weather(city: str) -> str:
    """查询指定城市的当前天气。

    参数:
        city: 城市中文名或拼音，如 '北京'、'Shanghai'、'Guangzhou'。
    """
    # 内置几个常见城市的经纬度（演示用），其他城市可通过百度/高德地理编码获得
    city_coords = {
        "北京": (39.9042, 116.4074),
        "上海": (31.2304, 121.4737),
        "广州": (23.1291, 113.2644),
        "深圳": (22.5431, 114.0579),
        "杭州": (30.2741, 120.1551),
        "成都": (30.5728, 104.0668),
        "beijing": (39.9042, 116.4074),
        "shanghai": (31.2304, 121.4737),
        "guangzhou": (23.1291, 113.2644),
        "shenzhen": (22.5431, 114.0579),
        "hangzhou": (30.2741, 120.1551),
        "chengdu": (30.5728, 104.0668),
    }
    coords = city_coords.get(city.lower(), city_coords.get(city))
    if coords is None:
        return f"❌ 暂不支持城市：{city}（演示环境内置了北上广深杭蓉）"
    lat, lon = coords
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current_weather=true"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        cw = data["current_weather"]
        temp = cw["temperature"]
        wind = cw["windspeed"]
        desc = {0: "晴朗", 1: "大致晴朗", 2: "多云", 3: "阴天"}.get(cw["weathercode"], "未知")
        return f"{city} 当前：{desc}，{temp}°C，风速 {wind} km/h"
    except Exception as e:
        return f"❌ 查询失败：{e}"

def calculator(expression: str) -> str:
    """四则运算计算器。

    参数:
        expression: 要计算的算术表达式，如 '12 * (5 + 3)'。
    """
    allowed = set("0123456789+-*/().% ")
    if any(ch not in allowed for ch in expression):
        return "❌ 表达式包含非法字符"
    try:
        return str(eval(expression))
    except Exception as e:
        return f"❌ 计算出错: {e}"


def current_time(tz: str = "UTC") -> str:
    """获取当前时间。

    参数:
        tz: 时区名称，如 'Asia/Shanghai' 或 'UTC'。默认 UTC。
    """
    from zoneinfo import ZoneInfo
    try:
        now = datetime.datetime.now(ZoneInfo(tz))
    except Exception:
        now = datetime.datetime.utcnow()
        tz = "UTC"
    return f"{now.strftime('%Y-%m-%d %H:%M:%S')} ({tz})"


# ============================================================
# 工具注册表配置
# ============================================================

def get_tools_spec():
    """返回 Function Calling 格式的工具说明书（给模型看的清单）。"""
    return [
        {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "做四则运算的简易计算器。当用户需要算数学表达式的值时可调用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "要计算的数学表达式，例如 '12 * (5 + 3)'",
                        }
                    },
                    "required": ["expression"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "current_time",
                "description": "获取当前时间。当用户询问现在是几点、今天日期时调用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tz": {
                            "type": "string",
                            "description": "时区，如 'Asia/Shanghai' 或 'UTC'，默认为 UTC",
                        }
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "查询指定城市当前天气。当用户问天气、温度时会调用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "城市名，如 '北京'、'Shanghai'、'Guangzhou'",
                        }
                    },
                    "required": ["city"],
                },
            },
        },
    ]


def get_tool_registry():
    """返回「工具名 -> 函数」映射，供 Agent 调度实际执行。"""
    return {
        "calculator": calculator,
        "current_time": current_time,
        "get_weather": get_weather,
    }
