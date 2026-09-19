﻿# win_ollama_setup.ps1 — Windows 主机：把 Ollama 配成本局域网的推理服务
#
# 2026/09/19 · 配合 docs/local-inference.md
#
# 用法（在 Windows 上以「管理员 PowerShell」运行）：
#     # 若文件是从网络/浏览器下载的，先解锁（否则可能被安全策略拦住）：
#     Unblock-File .\win_ollama_setup.ps1
#     Set-ExecutionPolicy -Scope Process Bypass -Force
#     .\win_ollama_setup.ps1
#
# 编码说明：本文件带 UTF-8 BOM —— Windows PowerShell 5.1 若无 BOM 会按
# 系统 ANSI（中文系统=GBK）解析，导致中文乱码甚至语法错误。请勿去掉 BOM。
#
# 它做四件事（都可重复运行，不会重复添加）：
#   1. 体检：系统版本 / AMD 驱动 / amdhip64 是否在
#   2. 设环境变量：OLLAMA_HOST 绑 0.0.0.0，让局域网能连
#   3. 加防火墙入站规则：放行 11434
#   4. 拉模型并验证 GPU 是否真的在干活
#
# ⚠️ 它不改注册表以外的东西，不删数据。唯一的系统级动作为「加一条防火墙规则」。

$ErrorActionPreference = "Stop"

function Info($m) { Write-Host "[·] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[✓] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[!] $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "[✗] $m" -ForegroundColor Red; exit 1 }

Write-Host "`n===== Ollama 局域网推理服务 · 安装与体检 =====" -ForegroundColor White

# ---------------------------------------------------------------
# 0. 管理员检查（加防火墙规则需要）
# ---------------------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Die "请用「管理员 PowerShell」运行本脚本（加防火墙规则需要）" }
Ok "管理员权限"

# ---------------------------------------------------------------
# 1. 体检
# ---------------------------------------------------------------
Write-Host "`n--- 1/4 体检 ---" -ForegroundColor White

$os = Get-CimInstance Win32_OperatingSystem
Info "系统：$($os.Caption) build $($os.BuildNumber)"
if ([int]$os.BuildNumber -lt 19045) {
    Warn "建议 Windows 10 22H2 (build 19045) 或更新；当前 $($os.BuildNumber)"
}

# AMD 的 HIP 运行时 dll —— 有它才有 GPU 加速
$hip = Get-ChildItem "C:\Windows\System32\amdhip64*.dll" -ErrorAction SilentlyContinue
if ($hip) {
    Ok "找到 HIP 运行时：$(($hip | ForEach-Object Name) -join ', ')"
} else {
    Warn "没找到 amdhip64*.dll —— 说明 AMD 驱动缺少 ROCm/HIP7 支持。"
    Warn "  → 去 AMD 官网装最新 Adrenalin 驱动（含 ROCm v7 / HIP7 栈），装完重启再来。"
    Warn "  → 兜底：新版 Ollama 默认启用 Vulkan，即使没有 HIP 也能跑 GPU（性能略低）。"
}

# 显卡型号（确认是 7900 GRE / gfx1100）
$gpus = Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name
Info "显卡：$($gpus -join ' / ')"

# ---------------------------------------------------------------
# 2. 环境变量
# ---------------------------------------------------------------
Write-Host "`n--- 2/4 环境变量（用户级）---" -ForegroundColor White

# 关键：默认只绑 127.0.0.1，局域网连不上。绑 0.0.0.0 才能被 Mac 访问。
$envVars = @{
    "OLLAMA_HOST"            = "0.0.0.0:11434"   # 让局域网可访问
    "OLLAMA_FLASH_ATTENTION" = "1"               # 省显存，长上下文收益明显
    "OLLAMA_KV_CACHE_TYPE"   = "q8_0"            # KV cache 量化，显存约减半
    "OLLAMA_CONTEXT_LENGTH"  = "8192"            # 够用即可，别让 KV 撑爆显存
    "OLLAMA_MAX_LOADED_MODELS" = "2"             # embedding + router 同时驻留
    "OLLAMA_NUM_PARALLEL"    = "2"
}
foreach ($k in $envVars.Keys) {
    $old = [Environment]::GetEnvironmentVariable($k, "User")
    if ($old -eq $envVars[$k]) {
        Info "$k 已是 $($envVars[$k])（跳过）"
    } else {
        [Environment]::SetEnvironmentVariable($k, $envVars[$k], "User")
        Ok "$k = $($envVars[$k])$(if ($old) { "  (原：$old)" })"
    }
}
Warn "环境变量对**已运行**的 Ollama 不生效 —— 稍后需要重启 Ollama（见第 4 步）"

# ---------------------------------------------------------------
# 3. 防火墙
# ---------------------------------------------------------------
Write-Host "`n--- 3/4 防火墙 ---" -ForegroundColor White
$ruleName = "Ollama LAN 11434"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Info "规则「$ruleName」已存在（跳过）"
} else {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound `
        -Protocol TCP -LocalPort 11434 -Action Allow -Profile Private | Out-Null
    Ok "已放行入站 TCP 11434（仅专用网络配置）"
    Warn "若 Mac 仍连不上，检查当前网络是否被标记为「公用」——公用配置下此规则不生效。"
}

# ---------------------------------------------------------------
# 4. 拉模型 + 验证
# ---------------------------------------------------------------
Write-Host "`n--- 4/4 模型与验证 ---" -ForegroundColor White

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Warn "没找到 ollama 命令 —— 请先装 Ollama for Windows（https://ollama.com/download）"
    Warn "装完重开一个 PowerShell 再跑本脚本。"
    exit 0
}
Ok "ollama 命令可用：$(ollama --version 2>&1 | Select-Object -First 1)"

# 重启 Ollama 托盘程序，让新环境变量生效
Info "重启 Ollama 进程以加载新环境变量…"
Get-Process ollama*, "ollama app" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-Process "ollama app.exe" -ErrorAction SilentlyContinue
Start-Sleep -Seconds 5

# embedding 模型：0.6B，输出 1024 维 —— 与本项目向量库维度一致
$embedModel = "qwen3-embedding:0.6b"
Info "拉取 embedding 模型：$embedModel（约 640MB）"
ollama pull $embedModel

Write-Host "`n--- 验证 ---" -ForegroundColor White
Info "本机自测 embedding 调用…"
try {
    $body = @{ model = $embedModel; input = "向量数据库可以实现语义搜索" } | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:11434/v1/embeddings" `
        -Method Post -Body $body -ContentType "application/json"
    $dim = $r.data[0].embedding.Count
    Ok "embedding 成功，输出维度 = $dim"
    if ($dim -ne 1024) {
        Warn "维度是 $dim（期望 1024）—— 与本项目向量库不一致，需要对齐后再用。"
    }
} catch {
    Warn "本机 embedding 调用失败：$_"
}

Info "GPU 占用检查（PROCESSOR 列应显示 100% GPU，而不是 100% CPU）："
ollama ps

Write-Host "`n===== 完成 =====" -ForegroundColor White
Write-Host "下一步在你 Mac 上执行：" -ForegroundColor Cyan
Write-Host "  1) 查本机 IP：Windows 上跑  ipconfig  → 找 192.168.x.x"
Write-Host "  2) Mac 上自检： .venv/bin/python scripts/check_local_llm_host.py http://192.168.x.x:11434"
Write-Host "  3) 跑 A/B 对比：.venv/bin/python eval_embedding_compare.py dashscope ollama"
Write-Host ""
