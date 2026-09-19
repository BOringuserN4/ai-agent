# -*- coding: utf-8 -*-
"""
scripts/check_local_llm_host.py — Mac 侧：诊断局域网 Ollama 主机是否可用

2026/09/19 · 配合 docs/local-inference.md

用法：
    .venv/bin/python scripts/check_local_llm_host.py http://192.168.1.50:11434
    .venv/bin/python scripts/check_local_llm_host.py          # 用 OLLAMA_HOST_URL

它按顺序查 5 件事，**哪一步断了一目了然**（而不是笼统地报「连不上」）：
    1. TCP 端口通不通（网络层）
    2. Ollama 版本接口有没有响应（服务层）
    3. 装了哪些模型（有没有我们要的 embedding 模型）
    4. embedding 能不能真跑通，输出维度对不对
    5. 延迟大概多少（含首次加载模型的时间）
"""
import os
import socket
import sys
import time
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import urllib.request
import urllib.error


def _get(url: str, timeout: float = 10.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _post(url: str, payload: dict, timeout: float = 120.0):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main():
    host = (sys.argv[1] if len(sys.argv) > 1
            else os.getenv("OLLAMA_HOST_URL", "http://127.0.0.1:11434")).rstrip("/")
    model = os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:0.6b")
    u = urlparse(host)
    hostname, port = u.hostname, (u.port or 11434)

    print("=" * 64)
    print(f"🔍 诊断 Ollama 主机：{host}")
    print("=" * 64)

    # 1) TCP
    print(f"\n[1/5] TCP 连通性 {hostname}:{port} …")
    t0 = time.time()
    try:
        with socket.create_connection((hostname, port), timeout=5) as s:
            s.close()
        print(f"   ✅ 端口开放（{(time.time()-t0)*1000:.0f}ms）")
    except Exception as e:
        print(f"   ❌ 连不上：{type(e).__name__}: {e}")
        print("\n   排查顺序：")
        print("     · Windows 上 Ollama 是否在跑？（托盘图标）")
        print("     · Windows 是否设了 OLLAMA_HOST=0.0.0.0:11434？（默认只绑 127.0.0.1）")
        print("     · 改完环境变量后**重启过 Ollama** 吗？（不重启不生效）")
        print("     · Windows 防火墙放行 11434 了吗？")
        print("     · 两台机器在同一网段吗？Mac 能不能 ping 通这台主机？")
        print(f"     · 先试 IPv6/换地址：{u.scheme}://127.0.0.1:{port}（在 Windows 本机跑）")
        return 1

    # 2) 版本
    print("\n[2/5] Ollama 服务 …")
    try:
        ver = _get(f"{host}/api/version")
        print(f"   ✅ 版本：{ver.get('version', '?')}")
    except Exception as e:
        print(f"   ❌ 服务无响应：{type(e).__name__}: {e}")
        print("      （端口通了但没有 HTTP 应答 —— 端口被别的程序占用？）")
        return 1

    # 3) 模型清单
    print("\n[3/5] 已安装模型 …")
    try:
        tags = _get(f"{host}/api/tags")
        names = [m.get("name") for m in (tags.get("models") or [])]
        if names:
            for n in names:
                mark = "  ← 🎯 目标模型" if n == model else ""
                print(f"   • {n}{mark}")
        else:
            print("   ⚠️  一个模型都没有")
        if model not in names:
            base = model.split(":")[0]
            near = [n for n in names if n.startswith(base)]
            if near:
                print(f"   ⚠️  没找到「{model}」，但有相近的：{near}")
            else:
                print(f"   ⚠️  没找到「{model}」→ 在 Windows 上跑：ollama pull {model}")
    except Exception as e:
        print(f"   ❌ 读取失败：{e}")

    # 4) embedding 实跑 + 维度
    print(f"\n[4/5] embedding 实跑（模型 {model}）…")
    print("   （首次会加载模型进显存，可能要几秒到几十秒）")
    t0 = time.time()
    try:
        r = _post(f"{host}/v1/embeddings",
                  {"model": model, "input": "向量数据库可以实现语义搜索"})
        first = time.time() - t0
        vec = r["data"][0]["embedding"]
        print(f"   ✅ 成功，维度 = {len(vec)}，首次耗时 {first:.1f}s")
        if len(vec) != 1024:
            print(f"   ⚠️  维度 {len(vec)} ≠ 项目期望的 1024 —— "
                  f"不能直接替换（向量库维度必须对齐）")
        # 二次调用测真实延迟（模型已驻留）
        t0 = time.time()
        for _ in range(3):
            _post(f"{host}/v1/embeddings",
                  {"model": model, "input": "这是一条用于测量延迟的中文句子"})
        print(f"   ⏱️  热态平均延迟：{(time.time()-t0)/3*1000:.0f} ms")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        print(f"   ❌ HTTP {e.code}：{body}")
        print("      常见原因：模型名写错 / 该模型不是 embedding 模型 / 维度参数不被支持")
        return 1
    except Exception as e:
        print(f"   ❌ 失败：{type(e).__name__}: {e}")
        return 1

    # 5) GPU 是否在用
    print("\n[5/5] GPU 占用 …")
    try:
        ps = _get(f"{host}/api/ps")
        models = ps.get("models") or []
        if not models:
            print("   （当前没有模型驻留显存）")
        for m in models:
            print(f"   • {m.get('name')}  size={m.get('size_vram', 0)/1e6:.0f}MB VRAM")
            if (m.get("size_vram") or 0) == 0:
                print("     ⚠️  size_vram=0 说明跑在 CPU 上！GPU 加速没生效。")
                print("        → Windows 上检查 amdhip64*.dll 是否存在 / 驱动是否含 ROCm7")
    except Exception as e:
        print(f"   （读不到：{e}）")

    print("\n" + "=" * 64)
    print("✅ 主机可用。下一步跑 A/B 对比：")
    print("   .venv/bin/python eval_embedding_compare.py dashscope ollama")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
