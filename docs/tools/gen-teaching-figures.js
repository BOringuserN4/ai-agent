#!/usr/bin/env node
// 教学总览 · 手绘风插图生成器（Notability / Excalidraw 风格）
// 复用 gen-notability.js 的手绘基元；输出 SVG + PNG 到 docs/diagrams/
// 用法：node docs/tools/gen-teaching-figures.js
const fs = require('fs');
const path = require('path');
const { Resvg } = require('@resvg/resvg-js');

const OUT = path.join(__dirname, '..', 'diagrams');
const W_CN = "ZCOOL KuaiLe, PingFang SC, sans-serif";
const W_EN = "Kalam, sans-serif";
const PAPER = '#fbf7ef';
const INK = '#3d3a34';
const NOTE_RED = '#e8590c';
const MARKER = { blue: '#5eb2f7', purple: '#9c8bf5', orange: '#f7a94b',
                 green: '#5fc97a', pink: '#f2809f' };

let R;
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
function setSeed(seed) { R = mkrng(seed); }
const rnd = (lo, hi) => lo + R() * (hi - lo);

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
    d += ` Q ${(px + (-uy) * amp * (R() * 2 - 1)).toFixed(1)}`
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

function handArrow(x1, y1, x2, y2, color = '#7a746b', dashed = false, sw = 2.2, bow = 8) {
  const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
  const dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy) || 1;
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
  const d = [
    `M ${x - pad} ${y - pad}`,
    `L ${x + w + pad} ${y - pad}`,
    `L ${x + w + pad} ${y + h + pad}`,
    `L ${x - pad} ${y + h + pad}`, 'Z',
  ].join(' ');
  return `<g transform="rotate(${rot.toFixed(2)} ${cx} ${cy})">
  <path d="${d}" fill="${color}" opacity="${op}" stroke="none"/>
  <path d="${d}" fill="${color}" opacity="${op * 0.5}" stroke="none"
        transform="translate(${rnd(-2, 2).toFixed(1)} ${rnd(-2, 2).toFixed(1)})"/>
</g>`;
}

function txt(x, y, s, o = {}) {
  const f = o.en ? W_EN : W_CN;
  const an = o.anchor ? ` text-anchor="${o.anchor}"` : '';
  const ls = o.ls ? ` letter-spacing="${o.ls}"` : '';
  const rot = o.rot ? ` transform="rotate(${o.rot} ${x} ${y})"` : '';
  return `<text x="${x}" y="${y}"${an}${ls}${rot} font-family="${f}"
    font-size="${o.size || 27}" font-weight="${o.weight || 400}"
    fill="${o.fill || INK}" opacity="${o.op || 1}">${s}</text>`;
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

function wrap(W, H, title, sub, body) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}"
  width="${W * 2}" height="${H * 2}">
${defs()}
<rect width="${W}" height="${H}" fill="${PAPER}"/>
<rect width="${W}" height="${H}" fill="url(#grid)"/>
<rect width="${W}" height="${H}" fill="url(#noisepat)"/>
<rect width="${W}" height="${H}" fill="url(#vignette)"/>
${txt(60, 76, title, { size: 46, weight: 700, ls: '2' })}
${txt(62, 104, sub, { en: true, size: 14, fill: '#8a8377' })}
${wavyUnderline(58, 120, Math.min(620, W - 120))}
${body}
</svg>`;
}

function box(x, y, w, h, title, sub, color, size = 24) {
  return `${markerBlock(x, y, w, h, color, 0.30)}
${handRect(x, y, w, h, '#4a453d', 2.6, 1.4)}
${txt(x + 16, y + 38, title, { size, weight: 700 })}
${txt(x + 16, y + 64, sub, { size: 14, fill: '#7d766a' })}`;
}

function save(name, svg, width = 2400) {
  fs.mkdirSync(OUT, { recursive: true });
  const svgPath = path.join(OUT, name + '.svg');
  const pngPath = path.join(OUT, name + '.png');
  fs.writeFileSync(svgPath, svg);
  const resvg = new Resvg(svg, {
    fitTo: { mode: 'width', value: width },
    font: { loadSystemFonts: true, defaultFontFamily: 'PingFang SC' },
  });
  fs.writeFileSync(pngPath, resvg.render().asPng());
  console.log('written:', svgPath, pngPath);
}

// ---------------------------------------------------------------- 图 1
function figAgentLoop() {
  setSeed(20261019);
  const W = 1400, H = 900;
  const g = [];
  // 中心
  g.push(box(500, 250, 400, 180, 'LLM（大脑）', '读懂 → 决策 → 写参数', MARKER.orange, 30));
  g.push(box(100, 285, 250, 110, 'Prompt', '角色 / 格式 / 约束', MARKER.blue, 25));
  g.push(box(1050, 285, 250, 110, '工具（手）', 'calculator / weather / MCP', MARKER.green, 25));
  g.push(box(500, 640, 400, 120, '记忆（上下文）', '短期 history + 长期检索', MARKER.purple, 25));
  // 箭头
  g.push(handArrow(352, 340, 496, 340, '#7a746b', false, 2.4));
  g.push(txt(362, 326, '角色约束', { size: 13, fill: '#8a8377' }));
  g.push(handArrow(904, 320, 1046, 320, '#7a746b', false, 2.4));
  g.push(txt(922, 290, 'function call', { en: true, size: 12.5, fill: '#8a8377' }));
  g.push(handArrow(1046, 370, 904, 370, '#7a746b', true, 2.2));
  g.push(txt(924, 402, '结果回流', { size: 13, fill: '#8a8377' }));
  g.push(handArrow(660, 434, 660, 636, '#7a746b', false, 2.4));
  g.push(txt(670, 520, '召回', { size: 13, fill: '#8a8377' }));
  g.push(handArrow(760, 636, 760, 434, '#7a746b', true, 2.2));
  g.push(txt(770, 590, '沉淀', { size: 13, fill: '#8a8377' }));
  // 循环圈
  g.push(handEllipse(700, 340, 280, 170, NOTE_RED, 2.2, 2));
  g.push(txt(700, 152, 'ReAct 循环', { size: 20, weight: 700, fill: NOTE_RED, anchor: 'middle', rot: -2 }));
  // 注记
  g.push(txt(80, 810, '去掉所有框架，Agent 就这四样：大脑、手、记忆、循环。', { size: 22, fill: '#5b554b' }));
  g.push(txt(80, 844, '其余模块（路由、评测、观测）都是加在它上面的成本。', { size: 18, fill: '#8a8377' }));
  g.push(star(1210, 690, 12, NOTE_RED));
  return wrap(W, H, 'Agent 的本质：一个循环 + 一份工具清单',
    'Agent = LLM + tools + memory + loop', g.join('\n'));
}

// ---------------------------------------------------------------- 图 2
function figPatterns() {
  setSeed(20261020);
  const W = 1600, H = 1100;
  const g = [];
  function panel(x, y, w, h, no, name, en, color, draw, note) {
    g.push(markerBlock(x, y, w, h, color, 0.12));
    g.push(handRect(x, y, w, h, '#4a453d', 2.4, 1.3));
    g.push(txt(x + 24, y + 46, no + '  ' + name, { size: 27, weight: 700 }));
    g.push(txt(x + 24, y + 70, en, { en: true, size: 13, fill: '#8a8377' }));
    draw(x, y, w, h);
    g.push(txt(x + 24, y + h - 22, note, { size: 14.5, fill: '#6d665b' }));
  }
  // Router
  panel(50, 170, 730, 410, '①', 'Router 路由', 'one dispatcher decides', MARKER.blue,
    (x, y, w, h) => {
      g.push(box(x + 30, y + 120, 170, 96, '用户问题', '一个请求', MARKER.blue, 19));
      g.push(box(x + 270, y + 120, 170, 96, 'Router', '只决策，不干活', MARKER.orange, 20));
      g.push(box(x + 510, y + 70, 190, 80, '数学专家', 'math', MARKER.green, 17));
      g.push(box(x + 510, y + 180, 190, 80, '天气专家', 'weather', MARKER.green, 17));
      g.push(handArrow(x + 202, y + 168, x + 266, y + 168, '#7a746b', false, 2));
      g.push(handArrow(x + 444, y + 152, x + 506, y + 110, '#7a746b', false, 2));
      g.push(handArrow(x + 444, y + 184, x + 506, y + 220, '#7a746b', false, 2));
    }, '代价：判断本身也要花 token；不确定时默认 solo。');
  // Pipeline
  panel(820, 170, 730, 410, '②', 'Pipeline 流水线', 'fixed order, code-controlled', MARKER.purple,
    (x, y, w, h) => {
      g.push(box(x + 30, y + 140, 190, 96, '第一步', '计算', MARKER.purple, 19));
      g.push(box(x + 270, y + 140, 190, 96, '第二步', '总结', MARKER.purple, 19));
      g.push(box(x + 510, y + 140, 180, 96, '第三步', '成稿', MARKER.purple, 19));
      g.push(handArrow(x + 222, y + 188, x + 266, y + 188, '#7a746b', false, 2));
      g.push(handArrow(x + 462, y + 188, x + 506, y + 188, '#7a746b', false, 2));
    }, '代价：流程定死，偏离预设就卡住；误差会累积。');
  // Fan-out
  panel(50, 620, 730, 410, '③', 'Fan-out 分发-汇聚', 'split, run in parallel, merge', MARKER.green,
    (x, y, w, h) => {
      g.push(box(x + 30, y + 150, 160, 96, '任务', '先切分', MARKER.green, 19));
      g.push(box(x + 280, y + 60, 150, 76, '子任务 1', '独立', MARKER.green, 17));
      g.push(box(x + 280, y + 160, 150, 76, '子任务 2', '独立', MARKER.green, 17));
      g.push(box(x + 280, y + 260, 150, 76, '子任务 3', '独立', MARKER.green, 17));
      g.push(box(x + 520, y + 160, 160, 96, '汇总', '只整合，不新增', MARKER.orange, 19));
      g.push(handArrow(x + 192, y + 196, x + 276, y + 100, '#7a746b', false, 2));
      g.push(handArrow(x + 192, y + 198, x + 276, y + 198, '#7a746b', false, 2));
      g.push(handArrow(x + 192, y + 200, x + 276, y + 296, '#7a746b', false, 2));
      g.push(handArrow(x + 432, y + 100, x + 516, y + 190, '#7a746b', false, 2));
      g.push(handArrow(x + 432, y + 198, x + 516, y + 202, '#7a746b', false, 2));
      g.push(handArrow(x + 432, y + 296, x + 516, y + 214, '#7a746b', false, 2));
    }, '成立条件：子任务独立 + 被等待的资源能吸收并发。');
  // EC
  panel(820, 620, 730, 410, '④', 'Evaluator-Critic', 'generate → critique → redo', MARKER.pink,
    (x, y, w, h) => {
      g.push(box(x + 30, y + 170, 180, 96, '生成', '第一版', MARKER.pink, 19));
      g.push(box(x + 280, y + 170, 180, 96, '批判', '独立立场', MARKER.orange, 19));
      g.push(box(x + 530, y + 170, 160, 96, '达标？', '代码封顶', MARKER.blue, 19));
      g.push(handArrow(x + 212, y + 218, x + 276, y + 218, '#7a746b', false, 2));
      g.push(handArrow(x + 462, y + 218, x + 526, y + 218, '#7a746b', false, 2));
      g.push(handArrow(x + 610, y + 268, x + 120, y + 268, '#7a746b', true, 2));
      g.push(txt(x + 300, y + 296, '不达标 → 带着批评重做', { size: 14, fill: '#8a8377' }));
    }, '代价：每轮多付生成 + 批判；有客观标准时改用代码验证。');
  g.push(txt(60, 1070, '四种模式不是四种“能力”，是四种“成本结构”。先问：单 Agent 到底做不到什么？', { size: 22, fill: '#5b554b' }));
  return wrap(W, H, '四种编排模式：一张图看懂',
    'Router / Pipeline / Fan-out / Evaluator-Critic', g.join('\n'));
}

// ---------------------------------------------------------------- 图 3
function figMemory() {
  setSeed(20261021);
  const W = 1600, H = 860;
  const g = [];
  g.push(txt(60, 200, '① 提问前：召回', { size: 30, weight: 700 }));
  g.push(txt(60, 228, '先找相关记忆，再让模型开口', { size: 16, fill: '#8a8377' }));
  g.push(box(80, 270, 220, 100, '用户问题', '这一轮输入', MARKER.blue, 20));
  g.push(box(380, 270, 240, 100, 'memory.search', 'embedding + top_k', MARKER.purple, 19));
  g.push(box(700, 270, 260, 100, '注入 system prompt', '相关片段进上下文', MARKER.orange, 18));
  g.push(box(1040, 270, 200, 100, 'LLM', '带着记忆回答', MARKER.green, 20));
  g.push(handArrow(302, 320, 376, 320, '#7a746b', false, 2.2));
  g.push(handArrow(622, 320, 696, 320, '#7a746b', false, 2.2));
  g.push(handArrow(962, 320, 1036, 320, '#7a746b', false, 2.2));
  g.push(txt(390, 410, '阈值 0.46：低于它不发（防污染）', { size: 14, fill: '#8a8377' }));
  g.push(txt(700, 410, 'top_k：最多发几条（控 token）', { size: 14, fill: '#8a8377' }));

  // 分隔
  g.push(`<path d="${jline(60, 470, 1540, 470)}" stroke="#b9b2a6" stroke-width="2" fill="none" opacity="0.6"/>`);

  g.push(txt(60, 540, '② 回答后：沉淀', { size: 30, weight: 700 }));
  g.push(txt(60, 568, '不是“无脑存”，先判断值不值得记', { size: 16, fill: '#8a8377' }));
  g.push(box(80, 610, 220, 100, '回答', '这一轮输出', MARKER.green, 20));
  g.push(box(380, 610, 240, 100, 'extractor', 'LLM 判断 keep', MARKER.orange, 20));
  g.push(box(700, 610, 260, 100, 'memory.add', '写 Chroma', MARKER.purple, 19));
  g.push(box(1040, 610, 200, 100, '后台线程', '不阻塞回答', MARKER.blue, 19));
  g.push(handArrow(302, 660, 376, 660, '#7a746b', false, 2.2));
  g.push(handArrow(622, 660, 696, 660, '#7a746b', false, 2.2));
  g.push(handArrow(962, 660, 1036, 660, '#7a746b', false, 2.2));
  g.push(txt(390, 750, '只记：明确偏好 / 个人信息 / 跨会话事实', { size: 14, fill: '#8a8377' }));
  g.push(txt(700, 750, '不记：寒暄 / 一次性计算 / 闲聊', { size: 14, fill: '#8a8377' }));

  g.push(txt(60, 830, '记忆不是“记住一切”，是两次有选择的动作：先召回，再沉淀。', { size: 22, fill: '#5b554b' }));
  return wrap(W, H, '记忆用两次：提问前召回，回答后沉淀',
    'two touches: recall before, persist after', g.join('\n'));
}

// ---------------------------------------------------------------- 图 4
function figEvalLoop() {
  setSeed(20261022);
  const W = 1500, H = 720;
  const g = [];
  const y = 280;
  const boxes = [
    { x: 70, t: '监控', s: 'Langfuse / Tracer' },
    { x: 360, t: '坏 case', s: '哪一步慢/贵/错' },
    { x: 650, t: '固化评测题', s: 'golden set + judge' },
    { x: 940, t: '修复', s: '改代码 / prompt' },
    { x: 1230, t: '回归验证', s: '同一题集重跑' },
  ];
  boxes.forEach((b, i) => {
    g.push(box(b.x, y, 200, 110, b.t, b.s, i % 2 ? MARKER.purple : MARKER.blue, 20));
    if (i < boxes.length - 1) {
      g.push(handArrow(b.x + 202, y + 56, boxes[i + 1].x - 6, y + 56, '#7a746b', false, 2.2));
    }
  });
  // 回环
  g.push(handArrow(1330, y + 140, 170, y + 140, '#7a746b', true, 2.2, 16));
  g.push(txt(620, y + 176, '回归通过 → 收口；回归失败 → 回到“坏 case”', { size: 15, fill: '#8a8377' }));
  g.push(txt(60, 560, '监控答“发生了什么”，评测答“对不对”。两件事，不能互相替代。', { size: 22, fill: '#5b554b' }));
  g.push(txt(60, 596, '闭环：坏 case 一旦复现，就固化成题；修完必须回归，否则下次还会踩。', { size: 18, fill: '#8a8377' }));
  return wrap(W, H, '评测闭环：从“看见”到“改对”',
    'monitor → reproduce → fix → regress', g.join('\n'));
}

// ---------------------------------------------------------------- 图 7 能力阶梯
function figLadder() {
  setSeed(20261023);
  const W = 1300, H = 900;
  const g = [];
  const rows = [
    ['L0', '最小 Agent', '88 行纯代码', 'minimal.py', MARKER.blue],
    ['L1', '+ 记忆', '+253 行', 'memory.py', MARKER.purple],
    ['L2', '+ 工具生态', '+375 行', 'mcp_bridge.py', MARKER.orange],
    ['L3', '+ 编排', '+510 行', 'multi_agent.py 等', MARKER.green],
    ['L4', '+ 评测与可观测', '+600 行', 'judge.py / eval_runner.py', MARKER.pink],
  ];
  rows.forEach((r, i) => {
    const y = 170 + i * 130;
    const x = 320 - i * 8;
    const w = 620 + i * 80;
    g.push(box(x, y, w, 92, `${r[0]}  ${r[1]}`, `${r[2]} · ${r[3]}`, r[4], 22));
    g.push(handEllipse(240, y + 46, 32, 32, '#7a746b', 2.2, 2));
    g.push(txt(240, y + 55, r[0], { size: 20, weight: 700, anchor: 'middle' }));
  });
  g.push(handArrow(170, 740, 170, 180, NOTE_RED, false, 2.4));
  g.push(txt(100, 460, '复杂度 / 能力', { size: 15, fill: '#8a8377', rot: -90, anchor: 'middle' }));
  g.push(txt(80, 810, '每一级都是独立可运行的程序；读一级懂一层，不要一次读全库。', { size: 21, fill: '#5b554b' }));
  g.push(txt(80, 844, '阶梯 0 是最小缺口，也是最大收益：88 行讲清 Agent 的本质。', { size: 17, fill: '#8a8377' }));
  return wrap(W, H, '能力阶梯：从 88 行到 4800 行', 'five runnable levels, one idea each', g.join('\n'));
}

// ---------------------------------------------------------------- 图 8 预算与收尾
function figBudget() {
  setSeed(20261024);
  const W = 1500, H = 720;
  const g = [];
  const y = 300;
  for (let i = 0; i < 8; i++) {
    const x = 120 + i * 145;
    const warn = i >= 6;
    g.push(handEllipse(x, y, 28, 28, warn ? NOTE_RED : '#7a746b', 2.2, warn ? 2 : 1));
    g.push(txt(x, y + 8, String(i + 1), { size: 21, weight: 700, anchor: 'middle' }));
    if (i < 7) g.push(handArrow(x + 32, y, x + 109, y, '#7a746b', false, 2));
  }
  g.push(handArrow(1250, y, 1310, y, '#7a746b', false, 2.2));
  g.push(box(1315, y - 45, 150, 90, '作答步', '只能作答，不许调工具', MARKER.green, 18));
  g.push(txt(980, 220, '剩余 ≤2 步：提醒收尾', { size: 16, weight: 700, fill: NOTE_RED }));
  g.push(txt(980, 246, '软提示只是建议', { size: 14, fill: '#8a8377' }));
  // 预算括号
  g.push(`<path d="M 120 380 L 120 410 L 1120 410 L 1120 380" fill="none" stroke="#7a746b" stroke-width="2" stroke-linecap="round"/>`);
  g.push(txt(620, 442, 'max_steps = 8（工具预算）', { size: 15, fill: '#6d665b', anchor: 'middle' }));
  g.push(txt(80, 560, '真正的 bug 不是“没有提醒”，是“最后一步被工具占满、没有作答的步”。', { size: 21, fill: '#5b554b' }));
  g.push(txt(80, 596, '改法：预算耗尽后多给一步作答步，并撤掉工具——改“可用动作”，不是加一句提醒。', { size: 17, fill: '#8a8377' }));
  return wrap(W, H, '预算与收尾：别等撞墙才停', 'warning + answer step, not just a reminder', g.join('\n'));
}

// ---------------------------------------------------------------- 图 9 MCP
function figMcp() {
  setSeed(20261025);
  const W = 1500, H = 820;
  const g = [];
  // 左：N×M
  g.push(markerBlock(50, 160, 680, 520, MARKER.pink, 0.10));
  g.push(handRect(50, 160, 680, 520, '#4a453d', 2.2, 1.2));
  g.push(txt(80, 206, '不用协议：N×M 份适配', { size: 24, weight: 700 }));
  g.push(txt(80, 232, '每个 Agent 都要单独接每个工具', { size: 14, fill: '#8a8377' }));
  const ax = [90, 250, 410], tx = [480, 590, 700];
  [0, 1, 2].forEach(i => {
    g.push(box(ax[i], 280, 120, 52, `Agent ${i + 1}`, '', MARKER.blue, 15));
  });
  // tools right column
  [0, 1, 2].forEach(i => {
    g.push(box(650, 280 + i * 100, 60, 60, `T${i + 1}`, '', MARKER.green, 15));
  });
  // 9 dashed links
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) {
    g.push(handArrow(ax[i] + 122, 306, 646, 310 + j * 100, '#b9b2a6', true, 1.2, 4));
  }
  // 右：N+M
  g.push(markerBlock(780, 160, 670, 520, MARKER.green, 0.10));
  g.push(handRect(780, 160, 670, 520, '#4a453d', 2.2, 1.2));
  g.push(txt(810, 206, '用 MCP：N+M 份适配', { size: 24, weight: 700 }));
  g.push(txt(810, 232, 'Agent 和工具各自实现一次协议', { size: 14, fill: '#8a8377' }));
  [0, 1, 2].forEach(i => {
    g.push(box(810, 280 + i * 100, 140, 60, `Agent ${i + 1}`, '', MARKER.blue, 15));
    g.push(box(1250, 280 + i * 100, 140, 60, `工具 ${i + 1}`, '', MARKER.green, 15));
    g.push(handArrow(954, 310 + i * 100, 1110, 360, '#7a746b', false, 1.8, 4));
    g.push(handArrow(1250, 310 + i * 100, 1180, 360, '#7a746b', false, 1.8, 4));
  });
  g.push(box(1110, 320, 70, 80, 'MCP', '插座', MARKER.orange, 18));
  g.push(txt(80, 740, '协议层很便宜（实测 0.69ms），贵的是工具声明每轮吃 token；按需裁剪省 42%。', { size: 20, fill: '#5b554b' }));
  return wrap(W, H, 'MCP：把 N×M 变成 N+M', 'one protocol, both sides implement once', g.join('\n'));
}

// ---------------------------------------------------------------- 图 10 串行 vs 并行
function figParallel() {
  setSeed(20261026);
  const W = 1500, H = 780;
  const g = [];
  g.push(txt(70, 190, '串行：一个接一个', { size: 24, weight: 700 }));
  ['工具 1', '工具 2', '工具 3'].forEach((t, i) => {
    const x = 180 + i * 200;
    g.push(box(x, 230, 170, 74, t, '串行', MARKER.blue, 18));
    if (i < 2) g.push(handArrow(x + 172, 267, x + 196, 267, '#7a746b', false, 2));
  });
  g.push(txt(800, 262, '总墙钟 5.11s', { size: 20, weight: 700, fill: NOTE_RED }));
  g.push(txt(70, 400, '并行：同时等', { size: 24, weight: 700 }));
  ['工具 1', '工具 2', '工具 3'].forEach((t, i) => {
    const y = 440 + i * 70;
    g.push(box(180, y, 540, 52, t, '同时发出', MARKER.green, 17));
  });
  g.push(`<path d="M 740 440 L 770 440 L 770 580 L 740 580" fill="none" stroke="#7a746b" stroke-width="2" stroke-linecap="round"/>`);
  g.push(txt(790, 514, '总墙钟 3.04s', { size: 20, weight: 700, fill: NOTE_RED }));
  g.push(txt(80, 700, '省的是墙钟，不是 token（实测 token 只 +3，符合预期）。', { size: 21, fill: '#5b554b' }));
  g.push(txt(80, 734, '成立条件：子任务独立 + 被等待的资源能吸收并发；单卡 GPU 会饱和。', { size: 17, fill: '#8a8377' }));
  return wrap(W, H, '串行 vs 并行：省的是墙钟', 'parallel wall-clock, not token', g.join('\n'));
}

// ---------------------------------------------------------------- 图 11 感知契约
function figObservation() {
  setSeed(20261027);
  const W = 1300, H = 760;
  const g = [];
  g.push(txt(70, 180, '裸字符串：程序只能猜', { size: 26, weight: 700, fill: NOTE_RED }));
  g.push(box(70, 220, 280, 100, '工具返回', '"MSFT: -1"', MARKER.blue, 18));
  g.push(box(420, 220, 300, 100, '下游代码', '正则/字符串解析', MARKER.orange, 18));
  g.push(box(790, 220, 300, 100, '结果', '−1 × 10 = −10.0', MARKER.pink, 18));
  g.push(handArrow(352, 270, 416, 270, '#7a746b', false, 2.2));
  g.push(handArrow(722, 270, 786, 270, '#7a746b', false, 2.2));
  g.push(txt(860, 350, '静默算错', { size: 20, weight: 700, fill: NOTE_RED }));

  g.push(txt(70, 450, '结构化契约：程序能分支', { size: 26, weight: 700, fill: '#2f7d4b' }));
  g.push(box(70, 490, 320, 110, '工具返回', '{ok:false, data:null, error:"超时"}', MARKER.green, 16));
  g.push(box(455, 490, 300, 110, '下游代码', 'if (!ok) 走失败分支', MARKER.orange, 18));
  g.push(box(820, 490, 300, 110, '结果', '正确失败，不参与计算', MARKER.green, 17));
  g.push(handArrow(392, 545, 451, 545, '#7a746b', false, 2.2));
  g.push(handArrow(757, 545, 816, 545, '#7a746b', false, 2.2));
  g.push(txt(80, 680, '强模型能识破异常（概率性）；程序消费不能靠概率。', { size: 21, fill: '#5b554b' }));
  g.push(txt(80, 714, '模型越强，越敢把判断交给下游程序——确定性契约反而更值钱。', { size: 17, fill: '#8a8377' }));
  return wrap(W, H, '感知契约：别让程序猜字符串', 'raw string vs {ok, data, error}', g.join('\n'));
}

// ---------------------------------------------------------------- 图 12 阈值空档
function figThreshold() {
  setSeed(20261028);
  const W = 1300, H = 650;
  const g = [];
  const x0 = 140, x1 = 1180;
  const sx = s => x0 + s * (x1 - x0);
  g.push(handArrow(x0, 560, x1, 560, '#7a746b', false, 2.2));
  ['0.0', '0.2', '0.4', '0.6', '0.8', '1.0'].forEach((t, i) => {
    const x = sx(i * 0.2);
    g.push(txt(x, 596, t, { size: 14, fill: '#8a8377', anchor: 'middle' }));
  });
  // 该召回
  g.push(markerBlock(sx(0.68), 250, sx(0.86) - sx(0.68), 48, MARKER.green, 0.35));
  g.push(handRect(sx(0.68), 250, sx(0.86) - sx(0.68), 48, '#4a453d', 2, 1.2));
  g.push(txt(sx(0.77), 228, '该召回 0.68–0.86', { size: 16, weight: 700, anchor: 'middle' }));
  // 不该召回
  g.push(markerBlock(sx(0.44), 430, sx(0.52) - sx(0.44), 48, MARKER.pink, 0.35));
  g.push(handRect(sx(0.44), 430, sx(0.52) - sx(0.44), 48, '#4a453d', 2, 1.2));
  g.push(txt(sx(0.48), 408, '不该召回 0.44–0.52', { size: 16, weight: 700, anchor: 'middle' }));
  // 阈值线
  g.push(`<path d="M ${sx(0.6)} 200 L ${sx(0.6)} 540" stroke="${NOTE_RED}" stroke-width="2.4" stroke-dasharray="8 7" fill="none"/>`);
  g.push(txt(sx(0.6), 182, '阈值 0.60（空档中点）', { size: 16, weight: 700, fill: NOTE_RED, anchor: 'middle' }));
  g.push(txt(sx(0.55), 330, '空档 0.16', { size: 16, weight: 700, fill: '#6d665b', anchor: 'end' }));
  g.push(txt(80, 500, '阈值贴着任何一组都不行：下次一有波动就翻车。', { size: 20, fill: '#5b554b' }));
  g.push(txt(80, 534, '分数跨模型不可比；换 embedding 必须重跑阈值扫描。', { size: 16, fill: '#8a8377' }));
  return wrap(W, H, '阈值怎么定：找两组分数之间的空档', 'threshold = midpoint of the gap', g.join('\n'));
}

// ---------------------------------------------------------------- 图 13 EC 数值 0/6
function figEcNumeric() {
  setSeed(20261029);
  const W = 1300, H = 700;
  const g = [];
  g.push(txt(650, 190, '0 / 6', { size: 68, weight: 700, fill: NOTE_RED, anchor: 'middle' }));
  const cards = [
    ['100', '✗'], ['771429', '✗'], ['48857', '✗'],
    ['9 → 771429', '✗'], ['13', '✗'], ['771429', '✗'],
  ];
  cards.forEach((c, i) => {
    const x = 70 + i * 195;
    g.push(box(x, 300, 170, 110, c[0], `run ${i + 1}`, MARKER.pink, 19));
    g.push(txt(x + 150, 340, c[1], { size: 30, weight: 700, fill: NOTE_RED, anchor: 'middle' }));
  });
  g.push(txt(80, 500, '六次里最刺眼的一次：首版 9 是对的，批判者说 11，重做后变成 771429。', { size: 20, fill: '#5b554b' }));
  g.push(txt(80, 536, '同模型批判者既会把对的判错，也会认同错的（13/13、771429/771429）。', { size: 17, fill: '#8a8377' }));
  g.push(txt(80, 604, '结论：有客观标准时，代码验证 > LLM 评委；EC 需要外部独立信号。', { size: 21, weight: 700, fill: NOTE_RED }));
  return wrap(W, H, '同模型 EC 在数值题上 0/6', 'same-model self-critique is not independent', g.join('\n'));
}

// ---------------------------------------------------------------- 图 14 能力×编排 2×2
function figMatrix() {
  setSeed(20261030);
  const W = 1300, H = 820;
  const g = [];
  g.push(txt(300, 180, 'solo', { size: 24, weight: 700, anchor: 'middle' }));
  g.push(txt(760, 180, 'EC', { size: 24, weight: 700, anchor: 'middle' }));
  g.push(txt(140, 360, '强', { size: 24, weight: 700, anchor: 'middle' }));
  g.push(txt(140, 600, '弱', { size: 24, weight: 700, anchor: 'middle' }));
  g.push(txt(80, 500, '模型能力', { size: 15, fill: '#8a8377', rot: -90, anchor: 'middle' }));
  g.push(txt(530, 740, '编排', { size: 15, fill: '#8a8377', anchor: 'middle' }));
  g.push(box(220, 230, 380, 220, '18 / 18', 'strong-solo：全对', MARKER.green, 30));
  g.push(box(680, 230, 380, 220, '—', '正测暂停', MARKER.pink, 30));
  g.push(box(220, 480, 380, 220, '11 / 18', 'weak-solo：T1/T6 掉分', MARKER.orange, 30));
  g.push(box(680, 480, 380, 220, '0 / 6', 'weak-ec：同模型批判不可靠', MARKER.pink, 30));
  g.push(txt(80, 780, '预筛已造出 gap（18/18 vs 11/18）；正测因 EC 不可靠暂停，先修“批判者独立性”。', { size: 19, fill: '#5b554b' }));
  return wrap(W, H, '能力 × 编排：2×2 对照', 'strong/weak × solo/EC', g.join('\n'));
}


save('教学-Agent本质', figAgentLoop(), 2200);
save('教学-四种编排', figPatterns(), 2400);
save('教学-记忆两次', figMemory(), 2400);
save('教学-评测闭环', figEvalLoop(), 2200);

// ---------------------------------------------------------------- 图 15 Router 预筛
function figRouterPrefilter() {
  setSeed(20261031);
  const W = 1500, H = 650;
  const g = [];
  g.push(box(60, 250, 220, 100, '用户输入', '这一轮问题', MARKER.blue, 20));
  g.push(box(350, 230, 300, 140, '规则预筛', '3 条判据 · 0 token', MARKER.orange, 22));
  g.push(txt(370, 400, '无连接词 / 单意图 / 无复杂度标记', { size: 14, fill: '#8a8377' }));
  g.push(handArrow(282, 300, 346, 300, '#7a746b', false, 2.2));
  g.push(handArrow(652, 270, 800, 200, '#7a746b', false, 2.2));
  g.push(handArrow(652, 330, 800, 430, '#7a746b', false, 2.2));
  g.push(box(810, 160, 300, 100, '明显不用拆', '86% 跳过', MARKER.green, 21));
  g.push(box(810, 380, 300, 100, '不确定 → Router', 'LLM 判断拆不拆', MARKER.pink, 21));
  g.push(handArrow(1112, 210, 1240, 280, '#7a746b', false, 2.2));
  g.push(handArrow(1112, 430, 1240, 320, '#7a746b', false, 2.2));
  g.push(box(1245, 250, 200, 100, 'solo / 专家', '执行', MARKER.purple, 21));
  g.push(txt(80, 540, '结果：86% 跳过 Router，14 条用例总 token −25%，答对率未退化。', { size: 21, fill: '#5b554b' }));
  g.push(txt(80, 574, '依据：误判“不拆”只降级（solo 接得住），工具漏选才是硬失败——后果不对称。', { size: 16, fill: '#8a8377' }));
  return wrap(W, H, 'Router 预筛：先花 0 token 判断', 'rule gate before the paid LLM decision', g.join('\n'));
}


save('教学-能力阶梯', figLadder(), 2200);
save('教学-预算与收尾', figBudget(), 2200);
save('教学-MCP', figMcp(), 2200);
save('教学-串行与并行', figParallel(), 2200);
save('教学-感知契约', figObservation(), 2200);
save('教学-阈值空档', figThreshold(), 2200);
save('教学-EC数值0of6', figEcNumeric(), 2200);
save('教学-能力编排矩阵', figMatrix(), 2200);

// ---------------------------------------------------------------- 图 16 集中式 vs 群聊
function figCentralVsChat() {
  setSeed(20261101);
  const W = 1400, H = 720;
  const g = [];
  // 左：集中式
  g.push(markerBlock(50, 160, 620, 430, MARKER.blue, 0.10));
  g.push(handRect(50, 160, 620, 430, '#4a453d', 2.2, 1.2));
  g.push(txt(80, 206, '集中式：一个协调者汇总', { size: 23, weight: 700 }));
  g.push(box(240, 250, 220, 80, '协调者', '看不到私有信息', MARKER.orange, 19));
  [0, 1, 2].forEach(i => {
    g.push(box(90 + i * 190, 400, 150, 64, `专家 ${i + 1}`, '各持一块信息', MARKER.blue, 16));
    g.push(handArrow(165 + i * 190, 396, 350, 334, '#7a746b', true, 1.6, 4));
  });
  g.push(txt(360, 540, '33%', { size: 48, weight: 700, fill: NOTE_RED, anchor: 'middle' }));
  g.push(txt(360, 570, '≈ 掷硬币', { size: 15, fill: '#8a8377', anchor: 'middle' }));
  // 右：群聊
  g.push(markerBlock(730, 160, 620, 430, MARKER.green, 0.10));
  g.push(handRect(730, 160, 620, 430, '#4a453d', 2.2, 1.2));
  g.push(txt(760, 206, 'Group Chat：共享频道', { size: 23, weight: 700 }));
  g.push(markerBlock(790, 300, 500, 54, MARKER.purple, 0.22));
  g.push(handRect(790, 300, 500, 54, '#4a453d', 1.8, 1.1));
  g.push(txt(1040, 334, '共享频道：每个人都能看到全部发言', { size: 15, fill: '#6d665b', anchor: 'middle' }));
  [0, 1, 2].forEach(i => {
    const x = 790 + i * 170;
    g.push(box(x, 410, 150, 64, `参与者 ${i + 1}`, '私有信息', MARKER.green, 16));
    g.push(handArrow(x + 75, 406, x + 75, 358, '#7a746b', false, 1.6, 3));
  });
  g.push(txt(1040, 540, '100%', { size: 48, weight: 700, fill: '#2f7d4b', anchor: 'middle' }));
  g.push(txt(1040, 570, '信息汇集 · 成本 1.25×', { size: 15, fill: '#8a8377', anchor: 'middle' }));
  g.push(txt(70, 660, '集中式不是崩溃，是“降级为单 Agent 自导自演”；信息分散时，它只能猜。', { size: 20, fill: '#5b554b' }));
  return wrap(W, H, '集中式 vs 群聊：信息分散时谁更行', '33% vs 100% on randomized truth', g.join('\n'));
}

// ---------------------------------------------------------------- 图 17 合同网
function figContractNet() {
  setSeed(20261102);
  const W = 1400, H = 650;
  const g = [];
  g.push(box(60, 250, 220, 100, '中央', '发标：这活谁干？', MARKER.orange, 20));
  g.push(txt(70, 390, '中央无法评估执行者的私有信息', { size: 14, fill: '#8a8377' }));
  [0, 1, 2].forEach(i => {
    const y = 150 + i * 150;
    g.push(box(390, y, 300, 110, `候选人 ${i + 1}`, '报价：能力 / 负载 / 工期', MARKER.blue, 18));
    g.push(handArrow(282, 300, 386, y + 55, '#7a746b', false, 1.8, 4));
    g.push(handArrow(692, y + 55, 820, 300, '#7a746b', false, 1.8, 4));
  });
  g.push(box(825, 250, 260, 100, '中标', '择优分配', MARKER.green, 22));
  g.push(txt(820, 390, '成本 ≈ 候选人数 × 单次（实测 ≈5×）', { size: 15, fill: '#8a8377' }));
  g.push(txt(70, 610, '适用：中央信息不足、需要逼出真实评估。中央能评估时，直接指派更省。', { size: 20, fill: '#5b554b' }));
  return wrap(W, H, 'Contract Net：发标 → 报价 → 中标', 'let the bidders reveal private information', g.join('\n'));
}

// ---------------------------------------------------------------- 图 18 黑板三臂
function figBlackboard() {
  setSeed(20261103);
  const W = 1400, H = 700;
  const g = [];
  const arms = [
    ['静态预排', '看不到日志就盲猜', '0 / 6', NOTE_RED, '20 选 3，几乎不可能命中'],
    ['单 Agent 反应', '先看告警，再决定查谁', '4 / 6', MARKER.orange, '优势来自“先观察、再决定”'],
    ['黑板', '日志触发子系统专家', '5 / 6', MARKER.green, '结构有没有增量？样本太小'],
  ];
  arms.forEach((a, i) => {
    const x = 60 + i * 450;
    g.push(markerBlock(x, 170, 400, 360, a[3], 0.10));
    g.push(handRect(x, 170, 400, 360, '#4a453d', 2.2, 1.2));
    g.push(txt(x + 24, 216, a[0], { size: 24, weight: 700 }));
    g.push(txt(x + 24, 250, a[1], { size: 15, fill: '#8a8377' }));
    g.push(txt(x + 200, 360, a[2], { size: 54, weight: 700, fill: a[3], anchor: 'middle' }));
    g.push(txt(x + 24, 460, a[4], { size: 14, fill: '#6d665b' }));
  });
  g.push(txt(70, 620, '关键变量是“反应式控制”，不是“黑板/多 Agent”结构；单 Agent 已经接近黑板。', { size: 20, fill: '#5b554b' }));
  return wrap(W, H, '黑板调查：三臂对照', 'static 0/6 · reactive 4/6 · blackboard 5/6', g.join('\n'));
}


save('教学-路由预筛', figRouterPrefilter(), 2200);

save('教学-集中vs群聊', figCentralVsChat(), 2200);
save('教学-合同网', figContractNet(), 2200);
save('教学-黑板三臂', figBlackboard(), 2200);
