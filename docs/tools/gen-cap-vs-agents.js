#!/usr/bin/env node
// 番外配图 · 模型能力 vs Agent 编排（Notability 手绘风）
// 用法：node gen-cap-vs-agents.js <A|B|C> <out.svg>
// 只改内容段（buildA/B/C）；基元与底材保持不动。
// 画幅均 1400 宽，2x 导出。种子固定以保证可复现。
const fs = require('fs');

// ---------------- 可复现随机 ----------------
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
const R = mkrng(20261014);
const rnd = (lo, hi) => lo + R() * (hi - lo);

// ---------------- 规格常量 ----------------
const PAPER = '#fbf7ef';
const F_CN = "ZCOOL KuaiLe, PingFang SC, sans-serif";
const F_EN = "Kalam, sans-serif";
const MARKER = { blue: '#5eb2f7', purple: '#9c8bf5', orange: '#f7a94b',
                 green: '#5fc97a', pink: '#f2809f', red: '#ef8a8a' };
const INK = '#3d3a34';
const NOTE_RED = '#e8590c';
const GREY = '#7a746b';
const PENCIL = '#8a8377';

const MODE = process.argv[2] || 'A';
const OUT = process.argv[3] || '/tmp/cap.svg';
let W = 1400, H = 900;
if (MODE === 'C') H = 760;

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
function handArrow(x1, y1, x2, y2, color = GREY, dashed = false, sw = 2.2) {
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
  const esc = String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return `<text x="${x}" y="${y}"${an}${ls}${rot} font-family="${f}"
    font-size="${o.size || 27}" font-weight="${o.weight || 400}"
    fill="${o.fill || INK}" opacity="${o.op || 1}">${esc}</text>`;
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

// ---------------- 新增：曲线 / 虚线 / 底材 ----------------
function dashLine(x1, y1, x2, y2, color, sw = 2) {
  return `<path d="M ${x1} ${y1} L ${x2} ${y2}" stroke="${color}" stroke-width="${sw}"
    stroke-dasharray="7 7" fill="none" opacity="0.8" stroke-linecap="round"/>`;
}
function curvePts(fx, fy, n) {
  const a = [];
  for (let i = 0; i <= n; i++) { const t = i / n; a.push([fx(t), fy(t)]); }
  return a;
}
function jcurve(pts, color, sw = 3.2) {
  const jp = pts.map(([x, y]) => [x + rnd(-1.1, 1.1), y + rnd(-1.1, 1.1)]);
  let d = `M ${jp[0][0].toFixed(1)} ${jp[0][1].toFixed(1)}`;
  for (let i = 1; i < jp.length - 1; i++) {
    const [x0, y0] = jp[i], [x1, y1] = jp[i + 1];
    d += ` Q ${x0.toFixed(1)} ${y0.toFixed(1)} ${((x0 + x1) / 2).toFixed(1)} ${((y0 + y1) / 2).toFixed(1)}`;
  }
  const last = jp[jp.length - 1];
  d += ` L ${last[0].toFixed(1)} ${last[1].toFixed(1)}`;
  return `<path d="${d}" fill="none" stroke="${color}" stroke-width="${sw}"
    stroke-linecap="round" opacity="0.95"/>`;
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
function paperBase() {
  return `<rect width="${W}" height="${H}" fill="${PAPER}"/>`
       + `<rect width="${W}" height="${H}" fill="url(#grid)"/>`
       + `<rect width="${W}" height="${H}" fill="url(#noisepat)"/>`
       + `<rect width="${W}" height="${H}" fill="url(#vignette)"/>`;
}
function tape(x, y) {
  return `<g transform="rotate(3.2 ${x + 115} ${y + 31})" opacity="0.55">
    <rect x="${x}" y="${y}" width="230" height="62" fill="#efe3cd"/>
    <rect x="${x}" y="${y}" width="230" height="62" fill="none"
      stroke="#d8c7a8" stroke-width="1.6" stroke-dasharray="6 5"/>
  </g>`;
}

// 通用坐标轴：原点(ox,oy)，右上角(xt,yt)
function axes(g, ox, oy, xt, yt, xlab, ylab) {
  g.push(handArrow(ox, oy, xt, oy, GREY, false, 2.6));
  g.push(handArrow(ox, oy, ox, yt, GREY, false, 2.6));
  g.push(txt(xt - 6, oy + 42, xlab, { size: 21, fill: GREY, anchor: 'end' }));
  g.push(txt(ox - 14, yt - 14, ylab, { size: 21, fill: GREY, anchor: 'middle' }));
}

// ===============================================================
// 图 A：两个轴 —— 价值随模型能力的两条曲线
// ===============================================================
function buildA() {
  const g = [paperBase()];
  g.push(txt(60, 80, '模型变强，两类脚手架的走向', { size: 52, weight: 700, ls: '2' }));
  g.push(txt(62, 108, 'One gets eaten · the other gets more valuable',
    { en: true, size: 16, fill: PENCIL }));
  g.push(wavyUnderline(58, 124, 470));
  g.push(tape(1120, 34));

  const ox = 190, oy = 760, xt = 1300, yt = 200;
  axes(g, ox, oy, xt, yt, '模型能力 →', '脚手架价值');

  // 0 线（价值为 0：加了反而有害）
  const zy = 590;
  g.push(dashLine(ox, zy, xt, zy, NOTE_RED, 2));
  g.push(txt(xt - 10, zy - 12, '价值 = 0（加了反而有害）',
    { size: 16, fill: NOTE_RED, anchor: 'end' }));

  // 推理轴：高 → 负（穿过 0 线）
  const rc = curvePts(t => ox + t * (xt - ox), t => 320 + t * 400, 30);
  g.push(jcurve(rc, MARKER.orange, 3.4));
  g.push(txt(300, 300, '推理轴', { size: 26, weight: 700, fill: '#c9761f' }));
  g.push(txt(300, 326, '规划 / 拆步 / 自我批评', { size: 18, fill: PENCIL }));

  // 工程轴：平稳上行
  const ec = curvePts(t => ox + t * (xt - ox), t => 560 - t * 250, 30);
  g.push(jcurve(ec, MARKER.blue, 3.4));
  g.push(txt(300, 585, '工程轴', { size: 26, weight: 700, fill: '#2f7fc4' }));
  g.push(txt(300, 611, '工具 / 上下文 / 记忆 / 可验证性', { size: 18, fill: PENCIL }));

  // 交点圈注
  const cx = ox + ((zy - 320) / 400) * (xt - ox), cy = zy;
  g.push(handEllipse(cx, cy, 26, 20, NOTE_RED, 2.6, 1));
  g.push(txt(cx + 6, cy + 58, '↘ 越强越吃亏', { size: 19, weight: 700, fill: NOTE_RED, rot: -3 }));
  g.push(txt(1030, 330, '越强越值钱 ↗', { size: 20, weight: 700, fill: '#2f7fc4', rot: 2 }));

  // 图例
  const lx = 190, ly = 842;
  g.push(txt(lx, ly - 16, '图例', { size: 19, weight: 700, rot: -0.6 }));
  g.push(jcurve([[lx + 4, ly + 8], [lx + 40, ly + 4], [lx + 76, ly + 8]], MARKER.orange, 3));
  g.push(txt(lx + 90, ly + 14, '推理类（被模型内化）', { size: 16 }));
  g.push(jcurve([[lx + 330, ly + 8], [lx + 366, ly + 12], [lx + 402, ly + 8]], MARKER.blue, 3));
  g.push(txt(lx + 416, ly + 14, '工程类（系统问题，吃不掉）', { size: 16 }));

  g.push(star(1340, 780, 11, NOTE_RED));
  g.push(star(120, 250, 9, NOTE_RED));
  return g;
}

// ===============================================================
// 图 B：长时程衰减 —— p 的几何崩塌
// ===============================================================
function buildB() {
  const g = [paperBase()];
  g.push(txt(60, 80, '长任务的崩塌：p<1 就是数学必然', { size: 50, weight: 700, ls: '1.5' }));  // 注意：txt() 内做实体转义
  g.push(txt(62, 108, 'Success ≈ p^steps · the driver is steps, not window size',
    { en: true, size: 15.5, fill: PENCIL }));
  g.push(wavyUnderline(58, 124, 560));
  g.push(tape(1120, 34));

  const ox = 200, oy = 760, xt = 1300, yt = 190;
  axes(g, ox, oy, xt, yt, '步数 →', '任务成功率');
  // Y 刻度
  [0, 0.5, 1.0].forEach(v => {
    const y = oy - v * (oy - 200);
    g.push(dashLine(ox, y, xt, y, '#cfc6b8', 1.4));
    g.push(txt(ox - 18, y + 6, Math.round(v * 100) + '%', { size: 15, fill: PENCIL, anchor: 'end' }));
  });

  const X = n => ox + (n / 20) * (xt - ox);          // 步数 0..20
  const Y = s => oy - s * (oy - 200);                 // 成功率 0..1
  const series = [[0.95, MARKER.blue, '#2f7fc4'], [0.90, MARKER.green, '#3f9c58'], [0.80, MARKER.red, '#c04a3f']];
  series.forEach(([p, col, labelCol], idx) => {
    const pts = [];
    for (let n = 0; n <= 20; n++) pts.push([X(n), Y(Math.pow(p, n))]);
    g.push(jcurve(pts, col, 3.2));
    g.push(txt(X(20) + 6, Y(Math.pow(p, 20)) + 6, 'p=' + p.toFixed(2),
      { size: 19, weight: 700, fill: labelCol }));
  });

  g.push(txt(240, 300, '每一步都可能出错；', { size: 22, fill: INK }));
  g.push(txt(240, 330, 'p 越接近 1，崩得越晚 —— 但从到不了 1。', { size: 22, fill: INK }));
  g.push(handEllipse(1050, 690, 150, 44, NOTE_RED, 2.4, 1));
  g.push(txt(1050, 697, '崩只是早晚', { size: 20, weight: 700, fill: NOTE_RED, anchor: 'middle', rot: -2 }));

  g.push(txt(200, 838, '⚠ 主因是「步数」，不是「上下文长度」；'
    + '限制窗口反而更糟（实测斜率 −0.69 vs −0.44）。', { size: 18, fill: '#b0472a', rot: -0.4 }));
  g.push(star(1355, 770, 11, NOTE_RED));
  g.push(star(130, 210, 9, NOTE_RED));
  return g;
}

// ===============================================================
// 图 C：自更正的两步 —— 找错是瓶颈，纠错要外部定位
// ===============================================================
function buildC() {
  const g = [paperBase()];
  g.push(txt(60, 80, '自更正的两步：找错 vs 纠错', { size: 50, weight: 700, ls: '2' }));
  g.push(txt(62, 108, 'Finding the error is the bottleneck; fixing it is easy',
    { en: true, size: 15.5, fill: PENCIL }));
  g.push(wavyUnderline(58, 124, 500));
  g.push(tape(1140, 34));

  const box = (x, y, w, h, col, title, sub, op = 0.34) => {
    const r = [];
    r.push(markerBlock(x, y, w, h, col, op));
    r.push(handRect(x, y, w, h, '#4a453d', 2.6, 1.4));
    r.push(txt(x + 16, y + h / 2 + (sub ? -2 : 8), title, { size: 22, weight: 700 }));
    if (sub) r.push(txt(x + 16, y + h / 2 + 24, sub, { size: 14, fill: PENCIL }));
    return r.join('\n');
  };
  const BH = 92;

  // 行 1：无外部反馈（红）
  const y1 = 190;
  g.push(txt(64, y1 + 52, '无外部反馈', { size: 23, weight: 700, fill: '#b0472a' }));
  g.push(txt(64, y1 + 76, 'self-critique', { en: true, size: 13, fill: PENCIL }));
  g.push(box(300, y1, 200, BH, MARKER.red, '回答', ''));
  g.push(handArrow(508, y1 + BH / 2, 606, y1 + BH / 2, GREY, false, 2.4));
  g.push(box(614, y1, 320, BH, MARKER.red, '找错？', '瓶颈：常找不到自己的错'));
  g.push(handArrow(942, y1 + BH / 2, 1040, y1 + BH / 2, GREY, false, 2.4));
  g.push(box(1048, y1, 296, BH, MARKER.red, '原地打转 / 更差', '', 0.28));
  g.push(txt(300, y1 + BH + 40, '✗ 让模型「再检查一遍」没用 —— 有时反而掉分。',
    { size: 18, fill: '#b0472a', rot: -0.4 }));

  // 行 2：有外部定位（绿）
  const y2 = 470;
  g.push(txt(64, y2 + 52, '有外部定位', { size: 23, weight: 700, fill: '#3f9c58' }));
  g.push(txt(64, y2 + 76, 'external signal', { en: true, size: 13, fill: PENCIL }));
  g.push(box(300, y2, 200, BH, MARKER.green, '回答', ''));
  g.push(handArrow(508, y2 + BH / 2, 606, y2 + BH / 2, GREY, false, 2.4));
  g.push(box(614, y2, 300, BH, MARKER.green, '外部给出错误位置', '工具 / 测试 / 验证'));
  g.push(handArrow(922, y2 + BH / 2, 1014, y2 + BH / 2, GREY, false, 2.4));
  g.push(box(1022, y2, 322, BH, MARKER.green, '纠错 → 改进', '只要告诉它错在哪，明显提升'));
  g.push(txt(300, y2 + BH + 40, '✓ 纠错能力很强 —— 缺的是「定位」，正是脚手架的用武之地。',
    { size: 18, fill: '#3f9c58', rot: -0.4 }));

  g.push(star(1355, 400, 11, NOTE_RED));
  g.push(star(130, 700, 9, NOTE_RED));
  return g;
}

// ===============================================================
const build = MODE === 'B' ? buildB : (MODE === 'C' ? buildC : buildA);
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}"
  width="${W * 2}" height="${H * 2}">
${defs()}
${build().join('\n')}
</svg>
`;
fs.writeFileSync(OUT, svg);
console.log('written:', OUT, `${W}x${H} -> ${W * 2}x${H * 2}`);
