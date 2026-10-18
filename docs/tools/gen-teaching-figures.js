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

save('教学-Agent本质', figAgentLoop(), 2200);
save('教学-四种编排', figPatterns(), 2400);
save('教学-记忆两次', figMemory(), 2400);
save('教学-评测闭环', figEvalLoop(), 2200);
