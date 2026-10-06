#!/usr/bin/env node
// Notability 手写笔记风格 · 软件系统分层架构图
// 严格按用户规格实现（2026/10/01）
// 画幅 1600x1200 → 2x 导出 3200x2400
// 用法：node gen-notability.js <out.svg>
const fs = require('fs');

// ---------------- 可复现随机 ----------------
function mkrng(seed) {
  let a = seed >>> 0;
  return () => {  // mulberry32
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const R = mkrng(20261001);
const rnd = (lo, hi) => lo + R() * (hi - lo);

// ---------------- 规格常量 ----------------
const W = 1600, H = 1200;
const PAPER = '#fbf7ef';
const F_CN = "ZCOOL KuaiLe, PingFang SC, sans-serif";
const F_EN = "Kalam, sans-serif";
const MARKER = { blue: '#5eb2f7', purple: '#9c8bf5', orange: '#f7a94b',
                 green: '#5fc97a', pink: '#f2809f' };
const INK = '#3d3a34';
const NOTE_RED = '#e8590c';

const out = [];

// ===============================================================
// 手绘基元
// ===============================================================
/** 抖动折线（带两端出头 overshoot） */
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
    d += ` Q ${(px - ux * 0 + (-uy) * amp * (R() * 2 - 1)).toFixed(1)}`
       + ` ${(py + ux * amp * (R() * 2 - 1)).toFixed(1)}`
       + ` ${px.toFixed(1)} ${py.toFixed(1)}`;
  }
  return d;
}

/** 双层笔触的手绘矩形（主笔 + 淡副笔） */
function handRect(x, y, w, h, color, mainW = 3, subW = 1.6) {
  const sides = [[x, y, x + w, y], [x + w, y, x + w, y + h],
                 [x + w, y + h, x, y + h], [x, y + h, x, y]];
  const paths = sides.map(([a, b, c, d]) => jline(a, b, c, d));
  // 副笔（错位一点，淡）
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

/** 手绘圆/椭圆（可多圈） */
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

/** 手绘箭头：二次贝塞尔弓形 + 双短线箭头头 */
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

/** 马克笔色块（半透明 + 轻微旋转，模拟涂色不齐） */
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
  const f = o.en ? F_EN : F_CN;
  const an = o.anchor ? ` text-anchor="${o.anchor}"` : '';
  const ls = o.ls ? ` letter-spacing="${o.ls}"` : '';
  const rot = o.rot ? ` transform="rotate(${o.rot} ${x} ${y})"` : '';
  return `<text x="${x}" y="${y}"${an}${ls}${rot} font-family="${f}"
    font-size="${o.size || 27}" font-weight="${o.weight || 400}"
    fill="${o.fill || INK}" opacity="${o.op || 1}">${s}</text>`;
}

/** 红色双波浪下划线 */
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
// 画布与底材
// ===============================================================
function defs() {
  return `<defs>
  <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
    <circle cx="1.6" cy="1.6" r="1.25" fill="#b9b2a6" opacity="0.5"/>
  </pattern>
  <!-- 纸张噪点：用**可平铺小图块**（256x256），而非整幅随机 —— 视觉几乎一致，
       但 PNG 压缩率大幅提升（整幅逐像素随机会让 3200x2400 涨到 7MB+） -->
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
// 内容：ai-agent 真实四层架构
// ===============================================================
const LAYERS = [
  { key: 'blue', name: '应用层', en: 'Application Layer',
    note: '谁来发起 · 都可被调用',
    mods: [['main.py', 'CLI 入口'], ['multi_agent', '路由 + 真并行'],
           ['pipeline', '串联执行'], ['evaluator_critic', '生成→批判→重做']] },
  { key: 'purple', name: '引擎层', en: 'Engine Layer',
    note: '主干 · core 是唯一引擎',
    mods: [['core', 'ReAct 循环'], ['roles', '角色定义'],
           ['json_mode', '结构化输出'], ['router_prefilter', '路由预筛']] },
  { key: 'orange', name: '能力层', en: 'Capability Layer',
    note: '有状态与外部接入',
    mods: [['memory', '长期记忆'], ['tools', '工具执行'],
           ['mcp_bridge', 'MCP 桥接'], ['extractor', '记忆过滤']] },
  { key: 'green', name: '组件层', en: 'Component Layer',
    note: '纯叶子 · 无内部依赖 · 可替换',
    mods: [['embedding_backends', '向量化'], ['tool_selector', '工具裁剪'],
           ['rerank', '精排(默认关)'], ['tracing', '轨迹记录']] },
];

const PINK_COL = { name: '可观测 · 评测', en: 'Observability',
  mods: [['tracing', '轨迹'], ['Langfuse', '上报'], ['judge', '评分'],
         ['golden_set', '题集']] };

function build() {
  const g = [];
  // 底材
  g.push(`<rect width="${W}" height="${H}" fill="${PAPER}"/>`);
  g.push(`<rect width="${W}" height="${H}" fill="url(#grid)"/>`);
  g.push(`<rect width="${W}" height="${H}" fill="url(#noisepat)"/>`);
  g.push(`<rect width="${W}" height="${H}" fill="url(#vignette)"/>`);

  // ---- 标题 ----
  g.push(txt(60, 78, 'ai-agent · 模块分层架构', { size: 54, weight: 700, ls: '2.5' }));
  g.push(txt(62, 106, 'LLM Agent Teaching Project — Layered Architecture',
    { en: true, size: 15.5, fill: '#8a8377' }));
  g.push(wavyUnderline(58, 122, 430));

  // ---- 胶带（右上角）----
  g.push(`<g transform="rotate(3.2 1430 66)" opacity="0.55">
    <rect x="1310" y="34" width="230" height="62" fill="#efe3cd"/>
    <rect x="1310" y="34" width="230" height="62" fill="none"
      stroke="#d8c7a8" stroke-width="1.6" stroke-dasharray="6 5"/>
    <path d="M1310 34 L1324 50 L1310 66" fill="none" stroke="#e0d2b8" stroke-width="1.4"/>
    <path d="M1540 34 L1526 50 L1540 66" fill="none" stroke="#e0d2b8" stroke-width="1.4"/>
  </g>`);

  // ---- 层 + 模块 ----
  // 布局：左侧留**独立栏**给层名（原先把层名与模块放同一区间 → 重叠 46px，被 QA 抓到）
  const GUT = 56, GUTW = 124;    // 层名栏 56..180
  const LX = 194, MW = 252, MGAP = 16;   // 模块区 194..1250
  const PX = 1304, PW = 262;     // 粉列 1304..1566（原 1270 → 与主列仅 20px，画不下箭头）
  const LW = MW * 4 + MGAP * 3;
  const y0 = 202, lh = 176;
  const MARK_X = GUT + 6;        // 层名起点（在独立栏内）

  LAYERS.forEach((L, i) => {
    const y = y0 + i * lh;
    const col = MARKER[L.key];
    // 层底色块
    g.push(markerBlock(GUT, y - 26, GUTW + LW + 36, lh - 26, col, 0.20));
    // 层名（左侧，手写）
    g.push(txt(MARK_X, y + 24, L.name, { size: 27, weight: 700, rot: -0.8 }));
    g.push(txt(MARK_X, y + 44, L.en.split(' ')[0], { en: true, size: 12, fill: '#8a8377', rot: -0.8 }));
    g.push(txt(MARK_X, y + 60, L.en.split(' ')[1] || '', { en: true, size: 12, fill: '#8a8377', rot: -0.8 }));
    // 备注按 9 字断行，避免越出左栏
    const nt = L.note.split(' · ');
    nt.slice(0, 2).forEach((line, k) =>
      g.push(txt(MARK_X, y + 80 + k * 15, line, { size: 11.5, fill: '#8a8377', rot: -0.8 })));
    // 模块
    L.mods.forEach(([n, s], j) => {
      const mw = MW, mh = 92;
      const x = LX + j * (mw + MGAP);
      const my = y - 8;
      g.push(markerBlock(x, my, mw, mh, col, 0.34));
      g.push(handRect(x, my, mw, mh, '#4a453d', 2.6, 1.4));
      g.push(txt(x + 16, my + 38, n, { size: 23, weight: 700 }));
      g.push(txt(x + 16, my + 64, s, { en: true, size: 14, fill: '#7d766a' }));
    });
  });

  // ---- 粉色贯穿列 ----
  const py = y0 - 26;
  const ph = 4 * lh - 26 + 26;
  g.push(markerBlock(PX, py, PW, ph, MARKER.pink, 0.20));
  g.push(handRect(PX, py, PW, ph, '#4a453d', 2.6, 1.4));
  g.push(txt(PX + PW / 2, py - 30, PINK_COL.name, { size: 24, weight: 700, anchor: 'middle' }));
  g.push(txt(PX + PW / 2, py - 10, PINK_COL.en, { en: true, size: 13,
    fill: '#8a8377', anchor: 'middle' }));
  PINK_COL.mods.forEach(([n, s], k) => {
    const mh = 92, my = py + 34 + k * (mh + 22);
    g.push(markerBlock(PX + 16, my, PW - 32, mh, MARKER.pink, 0.34));
    g.push(handRect(PX + 16, my, PW - 32, mh, '#4a453d', 2.4, 1.3));
    g.push(txt(PX + 30, my + 38, n, { size: 19, weight: 700 }));
    g.push(txt(PX + 30, my + 62, s, { en: true, size: 12.5, fill: '#7d766a' }));
  });

  // ---- 层间箭头 ----
  const ax = LX + MW + MGAP + MW / 2;   // 第 2 个模块中心（避开文字）
  for (let i = 0; i < LAYERS.length - 1; i++) {
    const yA = y0 + i * lh - 8 + 92, yB = y0 + (i + 1) * lh - 8;
    g.push(handArrow(ax + 120, yA + 4, ax + 120, yB - 4, '#7a746b', false, 2.2));
    g.push(txt(ax + 132, (yA + yB) / 2 + 5, '依赖', { size: 13, fill: '#8a8377' }));
  }
  // 粉列异步上报（虚线）
  // 异步上报：画在**层间空隙**里（原实现只有 2px 长且标签压进模块框，被 QA 抓到）
  const gapY = y0 - 8 + 92 + 42;          // 第 1 层模块底 → 第 2 层模块顶 之间
  // 起点必须在**层色块右缘之外**（色块右缘 = GUT+GUTW+LW+36 = 1272），否则箭头压在色块上
  g.push(handArrow(GUT + GUTW + LW + 36 + 6, gapY, PX - 6, gapY, '#7a746b', true, 2));
  g.push(txt((GUT + GUTW + LW + 36 + PX) / 2, gapY - 11, '异步', { size: 12,
    fill: '#8a8377', anchor: 'middle' }));

  // ---- 点饰：红星 ----
  g.push(star(1256, 214, 12, NOTE_RED));
  g.push(star(180, 762, 9, NOTE_RED));
  g.push(star(62, 900, 11, NOTE_RED));

  // ---- 图例（左下）----
  const lx = 56, ly = 1044;
  g.push(txt(lx, ly - 14, '图例', { size: 20, weight: 700, rot: -0.6 }));
  g.push(`<g>${handArrow(lx + 8, ly + 12, lx + 78, ly + 12, '#7a746b', false, 2)}</g>`);
  g.push(txt(lx + 92, ly + 18, '同步调用', { size: 17 }));
  g.push(`<g>${handArrow(lx + 200, ly + 12, lx + 270, ly + 12, '#7a746b', true, 2)}</g>`);
  g.push(txt(lx + 284, ly + 18, '异步消息', { size: 17 }));
  g.push(markerBlock(lx + 396, ly + 2, 34, 20, MARKER.green, 0.34));
  g.push(handRect(lx + 396, ly + 2, 34, 20, '#4a453d', 2, 1.2));
  g.push(txt(lx + 440, ly + 18, '分层职责', { size: 17 }));

  // ---- 右下技术注记（铅笔灰手写）----
  const nx = 700, ny = 1092;
  g.push(txt(nx, ny, '全部模块无状态可替换；', { size: 17, fill: '#8a8377', rot: -0.7 }));
  g.push(txt(nx, ny + 26, '记忆库按向量空间隔离，', { size: 17, fill: '#8a8377', rot: -0.5 }));
  g.push(txt(nx, ny + 52, '精排默认关闭（实测无收益）。', { size: 17, fill: '#8a8377', rot: -0.8 }));

  // ---- API 网关式旁注：核心入口 ----
  const gx = LX, gy = y0 - 8;   // 应用层第一个模块
  // 圈两圈（规格要求）；半径略收，避免碰到第 2 个模块
  g.push(handEllipse(gx + MW / 2, gy + 46, MW / 2 + 8, 60, NOTE_RED, 2.6, 2));
  // 旁注放在层带上方的空白带（原先前位于模块行 → 压住第 2 个模块，被 QA 抓到）
  g.push(txt(gx + MW + 40, y0 - 36, '↖ 统一入口！', { size: 20, weight: 700,
    fill: NOTE_RED, rot: -3 }));

  return g.join('\n');
}

const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}"
  width="${W * 2}" height="${H * 2}">
${defs()}
${build()}
</svg>
`;
fs.writeFileSync(process.argv[2] || '/tmp/notability.svg', svg);
console.log('written:', process.argv[2] || '/tmp/notability.svg');
