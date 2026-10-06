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
const W = 1600, H = 1200;            // 画幅（导出 2x = 3200x2400）
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
// 内容：运行时数据流（一次对话）
// ===============================================================
function build() {
  const g = [];
  // ---- 底材 ----
  g.push(`<rect width="${W}" height="${H}" fill="${PAPER}"/>`);
  g.push(`<rect width="${W}" height="${H}" fill="url(#grid)"/>`);
  g.push(`<rect width="${W}" height="${H}" fill="url(#noisepat)"/>`);
  g.push(`<rect width="${W}" height="${H}" fill="url(#vignette)"/>`);

  // ---- 标题 ----
  g.push(txt(60, 78, 'ai-agent · 运行时数据流', { size: 52, weight: 700, ls: '2.5' }));
  g.push(txt(62, 106, 'Runtime Data Flow — from user input to answer',
    { en: true, size: 15.5, fill: '#8a8377' }));
  g.push(wavyUnderline(58, 122, 400));

  // ---- 胶带（右上角）----
  g.push(`<g transform="rotate(3.2 1440 62)" opacity="0.55">
    <rect x="1330" y="30" width="230" height="60" fill="#efe3cd"/>
    <rect x="1330" y="30" width="230" height="60" fill="none"
      stroke="#d8c7a8" stroke-width="1.6" stroke-dasharray="6 5"/>
    <path d="M1330 30 L1344 46 L1330 62" fill="none" stroke="#e0d2b8" stroke-width="1.4"/>
    <path d="M1560 30 L1546 46 L1560 62" fill="none" stroke="#e0d2b8" stroke-width="1.4"/>
  </g>`);

  // ---- 主干 ----
  const SP = 660, BW = 540;
  const GRAY = '#c9d2dc', BLUE = MARKER.blue, GREEN = MARKER.green, ORANGE = MARKER.orange;

  /** 主链盒子：马克笔色块 + 手绘边框 + 标题/副标 */
  const step = (y, h, lines, color, accent) => {
    const x = SP - BW / 2;
    g.push(markerBlock(x, y, BW, h, color, 0.32));
    g.push(handRect(x, y, BW, h, '#4a453d', 2.6, 1.4));
    // 左侧强调条（手绘短竖线）
    g.push(`<path d="M ${x + 9} ${y + 12} L ${x + 9} ${y + h - 12}"
      stroke="${accent}" stroke-width="5" opacity="0.75" stroke-linecap="round"/>`);
    const st = y + h / 2 - (lines.length - 1) * 10.5;
    lines.forEach((l, i) => g.push(txt(x + 26, st + i * 21 + 6, l, {
      size: i === 0 ? 23 : 13.5, weight: i === 0 ? 700 : 400,
      fill: i === 0 ? INK : '#7d766a',
    })));
  };

  /** 侧枝小卡 */
  const sideCard = (x, y, w, h, lines, color) => {
    g.push(markerBlock(x, y, w, h, color, 0.30));
    g.push(handRect(x, y, w, h, '#4a453d', 2.3, 1.3));
    const st = y + h / 2 - (lines.length - 1) * 10;
    lines.forEach((l, i) => g.push(txt(x + 18, st + i * 20 + 5, l, {
      size: i === 0 ? 19 : 12.5, weight: i === 0 ? 700 : 400,
      fill: i === 0 ? INK : '#7d766a',
    })));
  };

  // ① 输入
  step(168, 62, ['用户输入'], GRAY, '#8b96a3');
  // ② 规划
  step(260, 84, ['multi_agent._plan()', '先跑规则预筛 → 不确定才问 LLM Router'], BLUE, BLUE);
  // ③ 记忆时点①
  step(386, 90, ['core.Agent.run()', '★ 记忆时点 ① — 提问前，先召回记忆'], GREEN, GREEN);
  // ④ ReAct
  step(518, 104, ['ReAct 循环（core 主干）', 'LLM 调用  ⇄  工具执行  ⇄  结果回流',
                  '每步记入 tracing，并上报 Langfuse'], ORANGE, ORANGE);
  // ⑤ 返回
  step(664, 62, ['返回回答'], GRAY, '#8b96a3');
  // ⑥ 记忆时点②
  step(758, 80, ['★ 记忆时点 ② — 回答后（后台线程，不阻塞）'], GREEN, GREEN);
  // ⑦ 写入
  step(870, 90, ['extractor.extract()  →  memory.add()',
                 '判断值不值得记 → 写入（同样走 embedding_backends）'], GREEN, GREEN);

  // ---- 主链箭头 ----
  const spine = (y1, y2) => g.push(handArrow(SP, y1, SP, y2, '#7a746b', false, 2.4));
  spine(230, 260); spine(344, 386); spine(476, 518);
  spine(622, 664); spine(726, 758); spine(838, 870);

  // ---- 侧枝：规划的两条出路 ----
  sideCard(96, 264, 250, 76, ['router_prefilter', '规则筛（零 token）'], BLUE);
  sideCard(976, 264, 250, 76, ['Router (LLM)', '判要不要拆任务'], BLUE);
  g.push(handArrow(SP - BW / 2, 300, 346, 302, '#7a746b', false, 2));
  g.push(handArrow(SP + BW / 2, 300, 976, 302, '#7a746b', false, 2));

  // ---- 侧枝：记忆召回 ----
  sideCard(66, 396, 262, 104,
    ['memory.search()', '· embedding_backends', '· ChromaDB top-K', '· rerank（默认关）'], GREEN);
  g.push(handArrow(SP - BW / 2, 434, 332, 448, '#7a746b', false, 2));
  g.push(txt(66, 528, '↑ 召回结果注入 system prompt', { size: 12, fill: '#7d766a' }));

  // ---- 点缀 ----
  g.push(star(1330, 220, 12, NOTE_RED));
  g.push(star(86, 620, 10, NOTE_RED));
  g.push(star(1560, 900, 11, NOTE_RED));

  // ---- 图例（左下）----
  const lx = 56, ly = 1010;
  g.push(txt(lx, ly - 14, '图例', { size: 20, weight: 700, rot: -0.6 }));
  g.push(handArrow(lx + 8, ly + 14, lx + 78, ly + 14, '#7a746b', false, 2.2));
  g.push(txt(lx + 92, ly + 20, '同步调用', { size: 17 }));
  g.push(handArrow(lx + 210, ly + 14, lx + 280, ly + 14, '#7a746b', true, 2.2));
  g.push(txt(lx + 294, ly + 20, '异步消息', { size: 17 }));
  g.push(star(lx + 418, ly + 12, 11, NOTE_RED));
  g.push(txt(lx + 440, ly + 20, '记忆时点', { size: 17 }));

  // ---- 右下技术注记 ----
  const nx = 700, ny = 1058;
  ['记忆被用两次：提问前召回注入，', '回答后抽取沉淀（后台线程）。']
    .forEach((line, k) => g.push(txt(nx, ny + k * 26, line,
      { size: 16, fill: '#8a8377', rot: -0.6 })));

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
