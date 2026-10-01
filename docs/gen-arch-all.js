#!/usr/bin/env node
// Notability 手写笔记风格 · 分层架构图生成器（模板）
// 用法：node notability-diagram.js <out.svg>
// 只改「内容」段（LAYERS / SIDE_COL / build() 里的文字与坐标），基元保持不变。
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
const R = mkrng(20261001);           // ← 种子；固定以保证可复现
const rnd = (lo, hi) => lo + R() * (hi - lo);

// ---------------- 规格常量 ----------------
const W = 1600, H = 1580;            // 画幅（导出 2x = 3200x2400）
const PAPER = '#fbf7ef';
const F_CN = "ZCOOL KuaiLe, PingFang SC, sans-serif";
const F_EN = "Kalam, sans-serif";
const MARKER = { blue: '#5eb2f7', purple: '#9c8bf5', orange: '#f7a94b',
                 green: '#5fc97a', pink: '#f2809f' };
const INK = '#3d3a34';
const NOTE_RED = '#e8590c';

const out = [];

// ===============================================================
// 手绘基元（保持不动）
// ===============================================================
/** 抖动折线；两端出头 overshoot 4~9px（模拟手绘「画过头」）*/
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

/** 双层笔触手绘矩形：主笔 3px + 副笔 1.6px@0.3 */
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

/** 手绘椭圆（rings>1 画多圈，错开角度）*/
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

/** 手绘箭头：二次贝塞尔弓形(bow=8) + 双短线箭头头；dashed=异步 */
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

/** 马克笔色块：半透明 + 旋转 ±0.5°（模拟涂色不齐）*/
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
  return `<text x="${x}" y="${y}"${an}${ls}${rot} font-family="${f}"
    font-size="${o.size || 27}" font-weight="${o.weight || 400}"
    fill="${o.fill || INK}" opacity="${o.op || 1}">${s}</text>`;
}

/** 标题下方红色双波浪下划线 */
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
  <!-- 噪点用可平铺小图块；整幅逐像素随机会让 3200x2400 涨到 7MB+ -->
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
// 内容：架构总览（分层结构 + 运行时数据流）
// ===============================================================
const LAYERS = [
  { key: 'blue', name: '应用层', en: 'Application', note: '谁来发起',
    mods: [['main.py', 'CLI 入口'], ['multi_agent', '路由 + 真并行'],
           ['pipeline', '串联执行'], ['evaluator_critic', '生成→批判→重做']] },
  { key: 'purple', name: '引擎层', en: 'Engine', note: '主干',
    mods: [['core', 'ReAct 循环'], ['roles', '角色定义'],
           ['json_mode', '结构化输出'], ['router_prefilter', '路由预筛']] },
  { key: 'orange', name: '能力层', en: 'Capability', note: '有状态',
    mods: [['memory', '长期记忆'], ['tools', '工具执行'],
           ['mcp_bridge', 'MCP 桥接'], ['extractor', '记忆过滤']] },
  { key: 'green', name: '组件层', en: 'Component', note: '纯叶子 · 可替换',
    mods: [['embedding_backends', '向量化'], ['tool_selector', '工具裁剪'],
           ['rerank', '精排(默认关)'], ['tracing', '轨迹记录']] },
];

const SIDE_COL = { name: '可观测 · 评测', en: 'Observability',
  mods: [['tracing', '轨迹'], ['Langfuse', '上报'],
         ['judge', '评分'], ['golden_set', '题集']] };

// 数据流 6 步： [标题, 副标, 主题色]
const STEPS = [
  ['用户输入', '', '#8b96a3'],
  ['multi_agent._plan()', '先跑规则预筛 → 不确定才问 LLM Router', '#5eb2f7'],
  ['core.Agent.run()', '★ 记忆时点 ① — 提问前，先召回记忆', '#5fc97a'],
  ['ReAct 循环（core 主干）', 'LLM 调用 ⇄ 工具执行 ⇄ 结果回流', '#f7a94b'],
  ['返回回答', '', '#8b96a3'],
  ['★ 记忆时点 ② — 回答后（后台线程）', 'extractor.extract() → memory.add()', '#5fc97a'],
];

function build() {
  const g = [];
  // ---- 底材 ----
  g.push(`<rect width="${W}" height="${H}" fill="${PAPER}"/>`);
  g.push(`<rect width="${W}" height="${H}" fill="url(#grid)"/>`);
  g.push(`<rect width="${W}" height="${H}" fill="url(#noisepat)"/>`);
  g.push(`<rect width="${W}" height="${H}" fill="url(#vignette)"/>`);

  // ---- 标题 ----
  g.push(txt(60, 76, 'ai-agent · 架构总览', { size: 50, weight: 700, ls: '2.5' }));
  g.push(txt(62, 102, 'Static Layers  +  Runtime Data Flow',
    { en: true, size: 15, fill: '#8a8377' }));
  g.push(wavyUnderline(58, 116, 360));

  // ---- 胶带（右上角）----
  g.push(`<g transform="rotate(3.2 1444 60)" opacity="0.55">
    <rect x="1334" y="28" width="220" height="58" fill="#efe3cd"/>
    <rect x="1334" y="28" width="220" height="58" fill="none"
      stroke="#d8c7a8" stroke-width="1.6" stroke-dasharray="6 5"/>
    <path d="M1334 28 L1348 44 L1334 60" fill="none" stroke="#e0d2b8" stroke-width="1.4"/>
    <path d="M1554 28 L1540 44 L1554 60" fill="none" stroke="#e0d2b8" stroke-width="1.4"/>
  </g>`);

  // =============================================================
  // 上半 · 分层结构
  // =============================================================
  g.push(txt(56, 148, '① 静态结构 · 分层', { size: 19, weight: 700, fill: '#7d766a' }));
  const GUT = 56, GUTW = 118, LX = 190, MW = 250, MGAP = 16;
  const PX = 1286, PW = 262, LW = MW * 4 + MGAP * 3;
  const y0 = 176, lh = 140, MH = 78;

  LAYERS.forEach((L, i) => {
    const y = y0 + i * lh, col = MARKER[L.key];
    g.push(markerBlock(GUT, y - 24, GUTW + LW + 22, lh - 32, col, 0.20));
    g.push(txt(GUT + 8, y + 20, L.name, { size: 24, weight: 700, rot: -0.8 }));
    g.push(txt(GUT + 8, y + 38, L.en, { en: true, size: 11, fill: '#8a8377', rot: -0.8 }));
    g.push(txt(GUT + 8, y + 54, L.note, { size: 11, fill: '#8a8377', rot: -0.8 }));
    L.mods.forEach(([n, s], j) => {
      const x = LX + j * (MW + MGAP), my = y - 4;
      g.push(markerBlock(x, my, MW, MH, col, 0.34));
      g.push(handRect(x, my, MW, MH, '#4a453d', 2.4, 1.3));
      g.push(txt(x + 14, my + 32, n, { size: 19, weight: 700 }));
      g.push(txt(x + 14, my + 55, s, { en: true, size: 12.5, fill: '#7d766a' }));
    });
  });

  // 粉列
  const py = y0 - 24, ph = 4 * lh - 32;
  g.push(markerBlock(PX, py, PW, ph, MARKER.pink, 0.20));
  g.push(handRect(PX, py, PW, ph, '#4a453d', 2.4, 1.3));
  g.push(txt(PX + PW / 2, py - 28, SIDE_COL.name, { size: 21, weight: 700, anchor: 'middle' }));
  g.push(txt(PX + PW / 2, py - 10, SIDE_COL.en, { en: true, size: 12, fill: '#8a8377', anchor: 'middle' }));
  SIDE_COL.mods.forEach(([n, s], k) => {
    const my = py + 30 + k * 96;
    g.push(markerBlock(PX + 14, my, PW - 28, MH, MARKER.pink, 0.34));
    g.push(handRect(PX + 14, my, PW - 28, MH, '#4a453d', 2.2, 1.2));
    g.push(txt(PX + 28, my + 32, n, { size: 17, weight: 700 }));
    g.push(txt(PX + 28, my + 55, s, { en: true, size: 12, fill: '#7d766a' }));
  });

  // 层间依赖箭头
  const ax = LX + MW + MGAP + MW / 2;
  for (let i = 0; i < LAYERS.length - 1; i++) {
    const yA = y0 + i * lh - 4 + MH, yB = y0 + (i + 1) * lh - 4;
    g.push(handArrow(ax, yA + 3, ax, yB - 3, '#7a746b', false, 2));
    g.push(txt(ax + 12, (yA + yB) / 2 + 5, '依赖', { size: 11.5, fill: '#8a8377' }));
  }
  // 注：原本此处有一条「异步上报」虚线箭头，但层色块右缘与粉列之间仅 6px，
  // 画不下（skill 记录的「空隙太窄」坑）。改为在右下注记里文字说明，
  // 并把「虚线=异步」放到数据流的后台线程那一步体现。

  // =============================================================
  // 下半 · 运行时数据流
  // =============================================================
  const dyLine = 736;
  g.push(txt(56, dyLine, '② 运行时 · 数据流', { size: 19, weight: 700, fill: '#7d766a' }));
  // 分隔虚线
  g.push(`<path d="M 56 ${dyLine + 14} L 1544 ${dyLine + 14}" stroke="#c9c0b0"
    stroke-width="1.6" stroke-dasharray="10 8" opacity="0.7"/>`);

  const SP = 800, FBW = 520, FH = 76, FGAP = 38, fy0 = 782;
  STEPS.forEach(([title, sub, accent], i) => {
    const y = fy0 + i * (FH + FGAP), x = SP - FBW / 2;
    g.push(markerBlock(x, y, FBW, FH, accent, 0.30));
    g.push(handRect(x, y, FBW, FH, '#4a453d', 2.4, 1.3));
    g.push(`<path d="M ${x + 9} ${y + 10} L ${x + 9} ${y + FH - 10}" stroke="${accent}"
      stroke-width="5" opacity="0.75" stroke-linecap="round"/>`);
    g.push(txt(x + 26, y + (sub ? 32 : 46), title, { size: 19, weight: 700 }));
    if (sub) g.push(txt(x + 26, y + 55, sub, { en: true, size: 12.5, fill: '#7d766a' }));
    if (i < STEPS.length - 1) {
      // 第 5→6 步是「回答后才异步沉淀记忆」，用虚线（图例：虚线=异步消息）
      const dashed = (i === 4);
      g.push(handArrow(SP, y + FH, SP, y + FH + FGAP, '#7a746b', dashed, 2.4));
      if (dashed) g.push(txt(SP + 14, y + FH + FGAP / 2 + 5, '异步（后台线程）',
        { size: 12, fill: '#8a8377' }));
    }
  });

  // 侧枝：规划的两条出路
  const s2 = fy0 + 1 * (FH + FGAP);   // step2 y
  g.push(markerBlock(120, s2 + 4, 300, 68, MARKER.blue, 0.30));
  g.push(handRect(120, s2 + 4, 300, 68, '#4a453d', 2.2, 1.2));
  g.push(txt(136, s2 + 32, 'router_prefilter', { size: 17, weight: 700 }));
  g.push(txt(136, s2 + 54, '规则筛（零 token）', { size: 12, fill: '#7d766a' }));
  g.push(handArrow(SP - FBW / 2, s2 + 38, 420, s2 + 38, '#7a746b', false, 2));

  // 侧枝：记忆召回
  const s3 = fy0 + 2 * (FH + FGAP);
  g.push(markerBlock(96, s3, 324, 96, MARKER.green, 0.30));
  g.push(handRect(96, s3, 324, 96, '#4a453d', 2.2, 1.2));
  g.push(txt(112, s3 + 28, 'memory.search()', { size: 17, weight: 700 }));
  ['· embedding_backends', '· ChromaDB top-K', '· rerank（默认关）']
    .forEach((t, k) => g.push(txt(112, s3 + 48 + k * 17, t, { size: 11.5, fill: '#7d766a' })));
  g.push(handArrow(SP - FBW / 2, s3 + 44, 420, s3 + 44, '#7a746b', false, 2));
  g.push(txt(96, s3 + 116, '↑ 召回结果注入 system prompt', { size: 11.5, fill: '#7d766a' }));

  // ---- 点缀 ----
  g.push(star(1498, 132, 11, NOTE_RED));
  g.push(star(74, 700, 9, NOTE_RED));
  g.push(star(1556, 1240, 11, NOTE_RED));

  // ---- 图例（左下，与数据流底对齐）----
  const lx = 96, ly = 1330;
  g.push(txt(lx, ly - 16, '图例', { size: 18, weight: 700, rot: -0.6 }));
  g.push(handArrow(lx + 4, ly + 10, lx + 68, ly + 10, '#7a746b', false, 2));
  g.push(txt(lx + 82, ly + 16, '同步调用', { size: 15.5 }));
  g.push(handArrow(lx + 190, ly + 10, lx + 254, ly + 10, '#7a746b', true, 2));
  g.push(txt(lx + 268, ly + 16, '异步消息', { size: 15.5 }));
  g.push(star(lx + 382, ly + 8, 10, NOTE_RED));
  g.push(txt(lx + 402, ly + 16, '记忆时点', { size: 15.5 }));

  // ---- 右下技术注记 ----
  const nx = 900, ny = 1492;
  g.push(txt(nx, ny, '上层依赖下层，下层不认识上层；记忆被用两次：提问前召回、回答后沉淀（异步）。',
    { size: 15, fill: '#8a8377', rot: -0.5 }));
  g.push(txt(nx, ny + 26, '可观测性（tracing / Langfuse）同样为异步上报，不阻塞主链。',
    { size: 15, fill: '#8a8377', rot: -0.4 }));

  return g.join('\n');
}

const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}"
  width="${W * 2}" height="${H * 2}">
${defs()}
${build()}
</svg>
`;
fs.writeFileSync(process.argv[2] || '/tmp/flow.svg', svg);
console.log('written:', process.argv[2] || '/tmp/flow.svg');
