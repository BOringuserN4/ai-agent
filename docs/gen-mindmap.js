#!/usr/bin/env node
// Notability 手写笔记风 · 学习历程思维脑图 生成器
// 用法：node gen-mindmap.js <out.svg>
// 只改「内容」段（CHAPTERS / build() 里的文字与坐标），基元保持不变。
const fs = require('fs');

// ---------------- 可复现随机（mulberry32，固定种子）----------------
function mkrng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const R = mkrng(20261006);           // ← 种子；固定以保证可复现
const rnd = (lo, hi) => lo + R() * (hi - lo);

// ---------------- 规格常量 ----------------
const W = 2760, H = 1820;            // 画幅（导出 2x = 5520x3640）
const PAPER = '#fbf7ef';
const F_CN = "ZCOOL KuaiLe, PingFang SC, sans-serif";
const F_EN = "Kalam, sans-serif";
const MARKER = { blue: '#5eb2f7', purple: '#9c8bf5', orange: '#f7a94b',
                 green: '#5fc97a', pink: '#f2809f', gray: '#c3bcae' };
const INK = '#3d3a34';
const NOTE_RED = '#e8590c';

const out = [];

// ===============================================================
// 手绘基元（保持不动）
// ===============================================================
function jline(x1, y1, x2, y2, over = 0) {
  const dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy) || 1;
  const ux = dx / L, uy = dy / L;
  const o1 = over || rnd(4, 9), o2 = over || rnd(4, 9);
  const ax = x1 - ux * o1, ay = y1 - uy * o1;
  const bx = x2 + ux * o2, by = y2 + uy * o2;
  const seg = Math.max(2, Math.round(L / 34));
  let d = `M ${ax.toFixed(1)} ${ay.toFixed(1)}`;
  for (let i = 1; i <= seg; i++) {
    const t = i / seg;
    const px = ax + (bx - ax) * t, py = ay + (by - ay) * t;
    const amp = (L / seg) * 0.055;
    d += ` Q ${(px - uy * amp * (R() * 2 - 1)).toFixed(1)}`
       + ` ${(py + ux * amp * (R() * 2 - 1)).toFixed(1)}`
       + ` ${px.toFixed(1)} ${py.toFixed(1)}`;
  }
  return d;
}

function handRect(x, y, w, h, color, mainW = 3, subW = 1.6) {
  const sides = [[x, y, x + w, y], [x + w, y, x + w, y + h],
                 [x + w, y + h, x, y + h], [x, y + h, x, y]];
  const paths = sides.map(([a, b, c, d]) => jline(a, b, c, d));
  const jx = rnd(-2.2, 2.2), jy = rnd(-2.2, 2.2);
  const paths2 = sides.map(([a, b, c, d]) => jline(a + jx, b + jy, c + jx, d + jy, 3));
  return `<g>
  <g stroke="${color}" stroke-width="${mainW}" fill="none" stroke-linecap="round" opacity="0.92">
    ${paths.map(d => `<path d="${d}"/>`).join('')}
  </g>
  <g stroke="${color}" stroke-width="${subW}" fill="none" stroke-linecap="round" opacity="0.3">
    ${paths2.map(d => `<path d="${d}"/>`).join('')}
  </g>
</g>`;
}

/** 虚线手绘矩形（用于「未学」留空卡片）*/
function dashedRect(x, y, w, h, color, sw = 2.4) {
  const sides = [[x, y, x + w, y], [x + w, y, x + w, y + h],
                 [x + w, y + h, x, y + h], [x, y + h, x, y]];
  const paths = sides.map(([a, b, c, d]) => jline(a, b, c, d));
  return `<g stroke="${color}" stroke-width="${sw}" fill="none" stroke-linecap="round"
      opacity="0.75" stroke-dasharray="11 9">
    ${paths.map(d => `<path d="${d}"/>`).join('')}
  </g>`;
}

function handEllipse(cx, cy, rx, ry, color, sw = 2.4, rings = 1) {
  let g = '';
  for (let k = 0; k < rings; k++) {
    const rx2 = rx + k * 5 + rnd(-2, 2), ry2 = ry + k * 5 + rnd(-2, 2);
    const rot = rnd(-0.18, 0.18) + k * 0.22;
    let d = '';
    const n = 16;
    for (let i = 0; i <= n; i++) {
      const t = (i / n) * Math.PI * 2;
      const jr = 1 + rnd(-0.035, 0.035);
      const px = cx + Math.cos(t + rot) * rx2 * jr;
      const py = cy + Math.sin(t + rot) * ry2 * jr;
      d += (i === 0 ? 'M' : 'L') + ` ${px.toFixed(1)} ${py.toFixed(1)} `;
    }
    d += 'Z';
    g += `<path d="${d}" fill="none" stroke="${color}" stroke-width="${sw - k * 0.4}" opacity="${k ? 0.55 : 0.9}"/>`;
  }
  return g;
}

function handArrow(x1, y1, x2, y2, color = '#7a746b', dashed = false, sw = 2.2) {
  const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
  const dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy) || 1;
  const bow = 8;
  const cx = mx + (-dy / L) * bow, cy = my + (dx / L) * bow;
  const d = `M ${x1} ${y1} Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${x2} ${y2}`;
  const ang = Math.atan2(y2 - cy, x2 - cx);
  const hl = 13;
  const a1 = ang + Math.PI - 0.42, a2 = ang + Math.PI + 0.42;
  const dash = dashed ? ' stroke-dasharray="8 7"' : '';
  return `<g stroke="${color}" fill="none" stroke-linecap="round">
  <path d="${d}" stroke-width="${sw}"${dash}/>
  <path d="M ${x2} ${y2} L ${(x2 + hl * Math.cos(a1)).toFixed(1)} ${(y2 + hl * Math.sin(a1)).toFixed(1)}
           M ${x2} ${y2} L ${(x2 + hl * Math.cos(a2)).toFixed(1)} ${(y2 + hl * Math.sin(a2)).toFixed(1)}"
        stroke-width="${sw}"/>
</g>`;
}

function markerBlock(x, y, w, h, color, op = 0.34) {
  const rot = rnd(-0.5, 0.5);
  const cx = x + w / 2, cy = y + h / 2;
  const pad = 3;
  const d = [`M ${x - pad} ${y - pad}`, `L ${x + w + pad} ${y - pad}`,
             `L ${x + w + pad} ${y + h + pad}`, `L ${x - pad} ${y + h + pad}`, 'Z'].join(' ');
  return `<g transform="rotate(${rot.toFixed(2)} ${cx} ${cy})">
  <path d="${d}" fill="${color}" opacity="${op}" stroke="none"/>
  <path d="${d}" fill="${color}" opacity="${op * 0.5}" stroke="none"
        transform="translate(${rnd(-2, 2).toFixed(1)} ${rnd(-2, 2).toFixed(1)})"/>
</g>`;
}

function txt(x, y, s, o = {}) {
  const f = o.en ? F_EN : F_CN;
  const an = o.anchor ? ` text-anchor="${o.anchor}"` : '';
  const ls = o.ls ? ` letter-spacing="${o.ls}"` : '';
  const rot = o.rot ? ` transform="rotate(${o.rot} ${x} ${y})"` : '';
  const safe = String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return `<text x="${x}" y="${y}"${an}${ls}${rot} font-family="${f}"
    font-size="${o.size || 27}" font-weight="${o.weight || 400}"
    fill="${o.fill || INK}" opacity="${o.op || 1}">${safe}</text>`;
}

function wavyUnderline(x, y, w) {
  const seg = (dy, o) => {
    let d = `M ${x} ${y + dy}`;
    const n = Math.round(w / 22);
    for (let i = 0; i < n; i++) {
      const x0 = x + (w / n) * i, x1 = x + (w / n) * (i + 1);
      d += ` Q ${(x0 + x1) / 2} ${y + dy - 9 * o}, ${x1} ${y + dy}`;
    }
    return d;
  };
  return `<g fill="none" stroke-linecap="round">
  <path d="${seg(0, 1)}" stroke="${NOTE_RED}" stroke-width="3.4" opacity="0.9"/>
  <path d="${seg(7, 0.8)}" stroke="${NOTE_RED}" stroke-width="2.2" opacity="0.4"/>
</g>`;
}

function star(cx, cy, r, color) {
  let d = '';
  for (let i = 0; i < 8; i++) {
    const rr = i % 2 ? r * 0.42 : r;
    const a = (Math.PI / 4) * i - Math.PI / 2;
    d += (i ? 'L' : 'M') + ` ${(cx + Math.cos(a) * rr).toFixed(1)} ${(cy + Math.sin(a) * rr).toFixed(1)} `;
  }
  return `<path d="${d}Z" fill="${color}" opacity="0.85"/>`;
}

// ===============================================================
// 底材（纸色 + 点阵 + 平铺噪点 + 渐晕）
// ===============================================================
function defs() {
  return `<defs>
  <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
    <circle cx="1.6" cy="1.6" r="1.25" fill="#b9b2a6" opacity="0.5"/>
  </pattern>
  <filter id="noisetile" x="0" y="0" width="256" height="256"
          filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse">
    <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3"
                  seed="11" stitchTiles="stitch"/>
    <feColorMatrix type="saturate" values="0"/>
  </filter>
  <pattern id="noisepat" width="256" height="256" patternUnits="userSpaceOnUse">
    <rect width="256" height="256" filter="url(#noisetile)" opacity="0.05"/>
  </pattern>
  <radialGradient id="vignette" cx="50%" cy="46%" r="72%">
    <stop offset="55%" stop-color="#fbf7ef" stop-opacity="0"/>
    <stop offset="100%" stop-color="#e6ddcd" stop-opacity="0.55"/>
  </radialGradient>
</defs>`;
}

// ===============================================================
// 内容（改这里）—— 学习历程思维脑图
// 每张专题卡：名称 + 「是什么」（它解决什么/怎么做）+ 「为什么这么干」（代价/判据）
// ===============================================================
const CHAPTERS = [
  { key: 'blue', name: '基础章', en: 'Basics', leaves: [
    ['Prompt 工程', 'system 定人格与输出格式', '指令不清 → 输出全飘'],
    ['工具 · 协议 MCP', '协议化工具调用（N+M）', 'N 框架 × M 工具 = N×M 适配'],
    ['最小 Agent（阶梯 0）', '88 行纯 ReAct 循环', '先做到「一口气读完」'],
  ]},
  { key: 'purple', name: '编排章', en: 'Orchestration', leaves: [
    ['Router 路由', '意图分类 → 分派专家', '跨域 ≠ 该拆，默认 solo'],
    ['Pipeline 流水线', '固定顺序串联，前出=后入', '线性流程最省心'],
    ['Fan-out 并行', '并行分发 + 汇聚', '独立且资源可吸收 → 省 41%'],
    ['Evaluator-Critic', '生成 → 批判 → 重做', '自己批自己 = 自我确认'],
    ['Planner-Executor', '先规划，再执行', '实测否决：小任务无病'],
    ['Hierarchical 层级', '层级 / 工人池（条件性）', '慢工具省 61–76%，快工具纯负债'],
  ]},
  { key: 'orange', name: '实战章', en: 'Practice', leaves: [
    ['记忆工程', '外置向量库，按需注入', '召回断层 → 文本增富修'],
    ['记忆切分粒度', '抽取补最近 3 轮上下文', '消解「它」指代（0/2 → 2/2）'],
    ['本地推理', 'Ollama 可插拔后端', '延迟 81ms vs 云端 158ms'],
  ]},
  { key: 'green', name: '评测章', en: 'Eval & Obs', leaves: [
    ['评测 + 可观测', 'Tracer + Langfuse + judge', '黑盒 → 知道「对不对」'],
    ['成本优化', '工具裁剪 / 预筛 / 清声明', '省 42% / 25% / 59%'],
  ]},
  { key: 'pink', name: '收尾章', en: 'Wrap-up', leaves: [
    ['资源感知', '截断 + 预算预警 + 收尾步', '软提示压不过惯性 → 撤工具'],
    ['架构图', '分层结构 + 运行时数据流', '讲清「为什么这么设计」'],
    ['学习总结', '项目主线收口', '回路一层层闭合'],
  ]},
  { key: 'gray', name: '未学 · 待续', en: 'To Learn', empty: true, leaves: [
    ['感知 - 行动结构化', '', ''],
    ['去中心化协商', '', ''],
    ['Group Chat / Blackboard', '', ''],
    ['Contract Net / Debate', '', ''],
    ['LangGraph 官方文档', '', ''],
  ]},
];

// ---------------- 布局常量 ----------------
const COLW = 396, COLGAP = 42;
const ROOT_W = 430, ROOT_H = 92, ROOT_Y = 150;
const BUS_Y = 292;
const HEAD_Y = 336, HEAD_H = 70;
const CARD_Y0 = 442, CARD_H = 172, CARD_STEP = 190;

function colX(i) {
  const total = CHAPTERS.length * COLW + (CHAPTERS.length - 1) * COLGAP;
  const m = (W - total) / 2;
  return m + i * (COLW + COLGAP);
}

function build() {
  const g = [];
  g.push(`<rect width="${W}" height="${H}" fill="${PAPER}"/>`);
  g.push(`<rect width="${W}" height="${H}" fill="url(#grid)"/>`);
  g.push(`<rect width="${W}" height="${H}" fill="url(#noisepat)"/>`);
  g.push(`<rect width="${W}" height="${H}" fill="url(#vignette)"/>`);

  // 标题 + 双波浪下划线
  g.push(txt(72, 82, 'AI Agent 学习历程 · 思维脑图', { size: 56, weight: 700, ls: '2.5' }));
  g.push(txt(76, 112, 'ai-agent Teaching Project — Learning Journey Mind Map',
    { en: true, size: 16, fill: '#8a8377' }));
  g.push(wavyUnderline(74, 128, 560));

  // 右上角胶带
  g.push(`<g transform="rotate(3.2 2530 62)" opacity="0.55">
    <rect x="2410" y="30" width="230" height="62" fill="#efe3cd"/>
    <rect x="2410" y="30" width="230" height="62" fill="none"
      stroke="#d8c7a8" stroke-width="1.6" stroke-dasharray="6 5"/>
    <path d="M2410 30 L2424 46 L2410 62" fill="none" stroke="#e0d2b8" stroke-width="1.4"/>
    <path d="M2640 30 L2626 46 L2640 62" fill="none" stroke="#e0d2b8" stroke-width="1.4"/>
  </g>`);

  // 根节点（中心）
  const rx = W / 2 - ROOT_W / 2;
  g.push(markerBlock(rx, ROOT_Y, ROOT_W, ROOT_H, MARKER.blue, 0.30));
  g.push(handRect(rx, ROOT_Y, ROOT_W, ROOT_H, '#4a453d', 3, 1.6));
  g.push(txt(W / 2, ROOT_Y + 40, 'AI Agent 学习历程', { size: 30, weight: 700, anchor: 'middle' }));
  g.push(txt(W / 2, ROOT_Y + 68, 'LLM Agent · 从 0 到编排 / 记忆 / 评测',
    { size: 15, fill: '#7d766a', anchor: 'middle' }));

  // 根 → 总线
  g.push(`<path d="${jline(W / 2, ROOT_Y + ROOT_H, W / 2, BUS_Y)}"
    stroke="#7a746b" stroke-width="2.6" fill="none" stroke-linecap="round"/>`);

  // 总线：从 col0 中心到 col5 中心
  const c0 = colX(0) + COLW / 2, cN = colX(CHAPTERS.length - 1) + COLW / 2;
  g.push(`<path d="${jline(c0, BUS_Y, cN, BUS_Y, 6)}"
    stroke="#7a746b" stroke-width="2.6" fill="none" stroke-linecap="round"/>`);

  // 各列
  CHAPTERS.forEach((C, i) => {
    const x = colX(i), cx = x + COLW / 2;
    const col = MARKER[C.key];
    const railX = x - 22;

    // 总线 → 列头 的竖箭头
    g.push(handArrow(cx, BUS_Y, cx, HEAD_Y - 6, '#7a746b', false, 2.4));

    // 列头
    g.push(markerBlock(x, HEAD_Y, COLW, HEAD_H, col, C.empty ? 0.16 : 0.30));
    if (C.empty) g.push(dashedRect(x, HEAD_Y, COLW, HEAD_H, '#8a8377', 2.4));
    else g.push(handRect(x, HEAD_Y, COLW, HEAD_H, '#4a453d', 2.8, 1.5));
    g.push(txt(x + 18, HEAD_Y + 40, C.name, { size: 24, weight: 700 }));
    g.push(txt(x + 18, HEAD_Y + 60, C.en + `  ·  ${C.leaves.length} 项`,
      { en: true, size: 13, fill: '#7d766a' }));

    // 左侧导轨 + 刻度
    const lastCy = CARD_Y0 + (C.leaves.length - 1) * CARD_STEP + CARD_H / 2;
    const headMid = HEAD_Y + HEAD_H / 2;
    g.push(`<path d="${jline(railX, headMid, railX, lastCy, 5)}"
      stroke="${C.empty ? '#b3aa9a' : '#7a746b'}" stroke-width="2.4"
      fill="none" stroke-linecap="round" ${C.empty ? 'stroke-dasharray="10 8"' : ''}/>`);
    g.push(`<path d="${jline(railX, headMid, x, headMid, 4)}"
      stroke="${C.empty ? '#b3aa9a' : '#7a746b'}" stroke-width="2.4" fill="none" stroke-linecap="round"/>`);

    // 卡片
    C.leaves.forEach(([name, what, why], j) => {
      const cy = CARD_Y0 + j * CARD_STEP, mid = cy + CARD_H / 2;
      g.push(`<path d="${jline(railX, mid, x, mid, 4)}"
        stroke="${C.empty ? '#b3aa9a' : '#7a746b'}" stroke-width="2.2" fill="none" stroke-linecap="round"/>`);
      if (C.empty) {
        g.push(dashedRect(x, cy, COLW, CARD_H, '#a89f8e', 2.2));
        g.push(txt(x + 20, cy + 44, name, { size: 19, weight: 700, fill: '#8a8377' }));
        g.push(txt(x + 20, cy + 82, '（待学 · 留空）', { size: 14, fill: '#b3aa9a' }));
      } else {
        g.push(markerBlock(x, cy, COLW, CARD_H, col, 0.32));
        g.push(handRect(x, cy, COLW, CARD_H, '#4a453d', 2.6, 1.4));
        g.push(txt(x + 18, cy + 38, name, { size: 20, weight: 700 }));
        // 是什么
        g.push(txt(x + 18, cy + 74, '是什么', { size: 13, weight: 700, fill: col }));
        g.push(txt(x + 82, cy + 74, what, { size: 15, fill: '#4a453d' }));
        // 为什么
        g.push(txt(x + 18, cy + 108, '为什么', { size: 13, weight: 700, fill: NOTE_RED }));
        g.push(txt(x + 82, cy + 108, why, { size: 15, fill: '#4a453d' }));
      }
    });
  });

  // 装饰星（避开根节点 1165..1595 / 150..242）
  g.push(star(760, 176, 13, NOTE_RED));
  g.push(star(2100, 158, 9, NOTE_RED));
  g.push(star(70, 1560, 11, NOTE_RED));

  // 图例（左下）
  const lx = 74, ly = 1660;
  g.push(txt(lx, ly - 22, '图例', { size: 20, weight: 700, rot: -0.6 }));
  g.push(txt(lx + 78, ly - 22, '·', { size: 20 }));
  g.push(txt(lx + 96, ly - 22, '每个专题 = 是什么（怎么做） + 为什么这么干（代价 / 判据）',
    { size: 16, fill: '#7d766a' }));
  g.push(markerBlock(lx, ly + 2, 34, 20, MARKER.purple, 0.32));
  g.push(handRect(lx, ly + 2, 34, 20, '#4a453d', 2, 1.2));
  g.push(txt(lx + 46, ly + 18, '已学专题', { size: 16 }));
  g.push(dashedRect(lx + 170, ly + 2, 34, 20, '#a89f8e', 2));
  g.push(txt(lx + 216, ly + 18, '未学（留空）', { size: 16, fill: '#8a8377' }));

  // 右下手写注记
  const nx = 1180, ny = 1640;
  ['主线：一层层闭合上一版敞开的回路。',
   '每个结论都要可复现；实测否决与实测通过一样值钱。',
   '“要加一层”的直觉，常掩盖一个更便宜的修法。']
    .forEach((line, k) => g.push(txt(nx, ny + k * 28, line,
      { size: 17, fill: '#8a8377', rot: -0.5 })));

  return g.join('\n');
}

const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}"
  width="${W * 2}" height="${H * 2}">
${defs()}
${build()}
</svg>
`;
fs.writeFileSync(process.argv[2] || '/tmp/mindmap.svg', svg);
console.log('written:', process.argv[2] || '/tmp/mindmap.svg');
