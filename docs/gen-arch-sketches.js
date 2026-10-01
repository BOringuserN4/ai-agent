#!/usr/bin/env node
// 手绘风架构图生成器（roughjs = Excalidraw 内部同款渲染库）
// 产出两张图：
//   1. 分层架构图  → docs/diagrams/architecture-sketch.svg
//   2. 运行时数据流 → docs/diagrams/architecture-flow.svg
//
// 用法：node gen-arch-sketches.js <输出目录>
const fs = require('fs');
const rough = require('roughjs');
const gen = rough.generator();

const FONT = '"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif';
const INK = '#1e293b', MUTED = '#64748b';

// ---------------------------------------------------------------
// 小工具：op 序列化 + 图元
// ---------------------------------------------------------------
function makeCanvas() {
  const out = [];
  const opsToPath = (ops) => ops.map(o => {
    const d = o.data;
    if (o.op === 'move') return `M ${d[0]} ${d[1]}`;
    if (o.op === 'lineTo') return `L ${d[0]} ${d[1]}`;
    if (o.op === 'bcurveTo') return `C ${d[0]} ${d[1]} ${d[2]} ${d[3]} ${d[4]} ${d[5]}`;
    return '';
  }).join(' ');

  function emit(drawable, stroke, sw, fill) {
    drawable.sets.forEach(set => {
      const d = opsToPath(set.ops);
      if (!d) return;
      if (set.type === 'path')
        out.push(`<path d="${d}" fill="none" stroke="${stroke}" stroke-width="${sw}" stroke-linecap="round"/>`);
      else if (set.type === 'fillPath')
        out.push(`<path d="${d}" fill="${fill}" stroke="none"/>`);
      else if (set.type === 'fillSketch')
        out.push(`<path d="${d}" fill="none" stroke="${fill}" stroke-width="${(set.options && set.options.fillWeight) || 0.6}"/>`);
    });
  }

  return {
    out,
    /** 圆角感的手绘框（用 rectangle，rough 自带抖动） */
    box(x, y, w, h, opt = {}) {
      emit(gen.rectangle(x, y, w, h, {
        roughness: opt.rough != null ? opt.rough : 1.4,
        bowing: opt.bow != null ? opt.bow : 1.0,
        stroke: opt.stroke || '#475569',
        strokeWidth: opt.sw != null ? opt.sw : 1.6,
        fill: opt.fill || 'none',
        fillStyle: 'solid',
        fillWeight: opt.fw != null ? opt.fw : 0.5,
      }), opt.stroke || '#475569', opt.sw != null ? opt.sw : 1.6, opt.fill || 'none');
    },
    line(x1, y1, x2, y2, opt = {}) {
      emit(gen.line(x1, y1, x2, y2, {
        roughness: opt.rough != null ? opt.rough : 1.1,
        bowing: 0.8,
        stroke: opt.stroke || '#94a3b8',
        strokeWidth: opt.sw != null ? opt.sw : 1.6,
      }), opt.stroke || '#94a3b8', opt.sw != null ? opt.sw : 1.6, 'none');
      if (opt.arrow !== false) {
        const ang = Math.atan2(y2 - y1, x2 - x1), L = opt.L || 12;
        const a1 = ang + Math.PI - 0.42, a2 = ang + Math.PI + 0.42;
        out.push(`<path d="M ${x2} ${y2} L ${x2 + L * Math.cos(a1)} ${y2 + L * Math.sin(a1)}`
          + ` M ${x2} ${y2} L ${x2 + L * Math.cos(a2)} ${y2 + L * Math.sin(a2)}"`
          + ` stroke="${opt.stroke || '#94a3b8'}" stroke-width="${opt.sw != null ? opt.sw : 1.6}"`
          + ` fill="none" stroke-linecap="round"/>`);
      }
    },
    text(x, y, s, opt = {}) {
      const anch = opt.anchor ? ` text-anchor="${opt.anchor}"` : '';
      out.push(`<text x="${x}" y="${y}"${anch} font-family='${FONT}'`
        + ` font-size="${opt.size || 14}" font-weight="${opt.weight || 400}"`
        + ` fill="${opt.fill || INK}">${s}</text>`);
    },
    /** 居中多行标签框 */
    labelBox(x, y, w, h, lines, opt = {}) {
      this.box(x, y, w, h, opt);
      const startY = y + h / 2 - (lines.length - 1) * 9.5;
      lines.forEach((ln, i) => this.text(x + w / 2, startY + i * 19 + 5, ln, {
        anchor: 'middle', size: i === 0 ? (opt.size0 || 16) : (opt.size1 || 12.5),
        weight: i === 0 ? 600 : 400, fill: i === 0 ? INK : MUTED,
      }));
    },
  };
}

function wrap(W, H, body, title, subtitle) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}"`
    + ` width="${W}" height="${H}">\n<rect width="${W}" height="${H}" fill="#ffffff"/>\n`
    + body.join('\n') + `\n<text x="40" y="48" font-family='${FONT}' font-size="26"`
    + ` font-weight="800" fill="${INK}">${title}</text>\n`
    + `<text x="40" y="72" font-family='${FONT}' font-size="14" fill="${MUTED}">${subtitle}</text>\n</svg>\n`;
}

// ===============================================================
// 图 1 · 分层架构图
// 修正：extractor / tools / tracing 归入**组件层**（AST 证实为纯叶子），
//       我原先在文字回答里把它们放进了「能力层」，本次以事实为准。
// ===============================================================
function layerDiagram() {
  const W = 1720, H = 1010, DX = 40;
  const c = makeCanvas();
  const LX = 40, LW = 1640;

  const band = (y, h, title, fill, stroke) => {
    c.box(LX, y, LW, h, { fill, stroke, sw: 2, rough: 0.7, bow: 0.5, fw: 0.55 });
    c.text(LX + 14, y - 9, title, { size: 15, weight: 700, fill: stroke });
  };

  // ---- 应用层 ----
  band(110 + DX, 120, '① 应用层 · 谁都可以调它们', '#dbeafe', '#2563eb');
  [['main.py', 'CLI 入口'], ['multi_agent', '路由 + 真并行'],
   ['pipeline', '串联执行'], ['evaluator_critic', '生成→批判→重做']]
    .forEach(([n, d], i) =>
      c.labelBox(60 + i * 400, 155 + DX, 380, 62, [n, d],
        { fill: '#eff6ff', rough: 1.5 }));

  // ---- 引擎层 ----
  band(290 + DX, 118, '② 引擎层 · 主干', '#fef3c7', '#d97706');
  [['core', 'ReAct 循环 · 唯一主干'], ['roles', '角色定义 → 产 Agent'],
   ['json_mode', '结构化输出']]
    .forEach(([n, d], i) =>
      c.labelBox(200 + i * 460, 335 + DX, 420, 62, [n, d],
        { fill: '#fffbeb', rough: 1.5 }));

  // ---- 能力层 ----
  band(468 + DX, 118, '③ 能力层 · 有状态', '#dcfce7', '#16a34a');
  c.labelBox(610, 512 + DX, 500, 62,
    ['memory', '长期记忆：检索 + 阈值闸门 + 空间隔离'],
    { fill: '#f0fdf4', rough: 1.5 });

  // ---- 组件层 ----
  band(646 + DX, 280, '④ 组件层 · 纯叶子（10 个，无内部依赖，可独立测试/替换）',
    '#f1f5f9', '#64748b');
  const row1 = ['embedding_backends', 'extractor', 'tools', 'tracing', 'router_prefilter'];
  const row2 = ['rerank', 'tool_selector', 'mcp_bridge', 'judge', 'golden_set'];
  [row1, row2].forEach((row, r) => row.forEach((n, i) =>
    c.labelBox(60 + i * 324, 692 + DX + r * 104, 300, 80, [n],
      { fill: '#ffffff', rough: 1.6, size0: 14.5 })));

  // ---- 层间依赖箭头（层→层）----
  const mid = LX + LW / 2;
  c.line(mid, 230 + DX, mid, 290 + DX, { stroke: '#94a3b8', sw: 1.8 });
  c.line(mid, 408 + DX, mid, 468 + DX, { stroke: '#94a3b8', sw: 1.8 });
  c.line(mid, 586 + DX, mid, 646 + DX, { stroke: '#94a3b8', sw: 1.8 });
  // 依赖方向提示
  [[252 + DX, '依赖'], [430 + DX, '依赖'], [608 + DX, '依赖']]
    .forEach(([y, t]) => c.text(mid + 12, y, t, { size: 12, fill: MUTED }));

  return wrap(W, H, c.out, 'ai-agent · 分层架构图（手绘风）',
    '上层依赖下层，下层不认识上层 —— 越底层越「无知」，越上层越「知道全局」');
}

// ===============================================================
// 图 2 · 运行时数据流（一次对话）
// ===============================================================
function flowDiagram() {
  const W = 1340, H = 1560, DX = 30;
  const c = makeCanvas();
  const SPINE = 430;          // 主干 x
  const AW = 460;             // 主干框宽

  const main = (y, h, lines, fill, stroke) =>
    c.labelBox(SPINE - AW / 2, y, AW, h, lines,
      { fill, stroke, rough: 1.4, sw: fund(stroke) });

  function fund(s) { return 1.8; }

  // ① 用户输入
  c.labelBox(SPINE - 110, 105 + DX, 220, 56, ['用户输入'],
    { fill: '#e2e8f0', rough: 1.6, size0: 16 });
  c.line(SPINE, 161 + DX, SPINE, 205 + DX, { sw: 1.8 });

  // ② 规划（含规则预筛分支）
  main(205 + DX, 84, ['multi_agent._plan()', '先规则预筛，再决定要不要问 LLM'],
    '#dbeafe', '#2563eb');
  // 侧枝：预筛
  c.line(SPINE - AW / 2, 247 + DX, 130, 247 + DX, { sw: 1.6, arrow: false });
  c.line(130, 247 + DX, 130, 300 + DX, { sw: 1.6 });
  c.labelBox(30, 300 + DX, 200, 76, ['router_prefilter', '规则筛（零 token）'],
    { fill: '#f1f5f9', rough: 1.5, size0: 14 });
  // 侧枝：Router
  c.line(SPINE + AW / 2, 247 + DX, W - 130, 247 + DX, { sw: 1.6, arrow: false });
  c.line(W - 130, 247 + DX, W - 130, 300 + DX, { sw: 1.6 });
  c.labelBox(W - 230, 300 + DX, 200, 76, ['Router (LLM)', '判要不要拆'],
    { fill: '#f1f5f9', rough: 1.5, size0: 14 });

  c.line(SPINE, 289 + DX, SPINE, 405 + DX, { sw: 1.8 });

  // ③ core.run + 记忆时点①
  main(405 + DX, 92, ['core.Agent.run()', '★ 记忆时点 ①：提问前'],
    '#fef3c7', '#d97706');
  // 记忆侧枝
  c.line(SPINE - AW / 2, 451 + DX, 130, 451 + DX, { sw: 1.6, arrow: false });
  c.line(130, 451 + DX, 130, 512 + DX, { sw: 1.6 });
  c.labelBox(30, 512 + DX, 200, 104,
    ['memory.search()', '· embedding_backends', '· ChromaDB top-K', '· rerank（默认关）'],
    { fill: '#dcfce7', rough: 1.5, size0: 13.5, size1: 11.5 });
  c.line(230, 564 + DX, SPINE - AW / 2, 564 + DX, { sw: 1.6 });
  // 说明放在侧枝框**下方**（原先右对齐会压进框内，被 QA 抓到）
  c.text(30, 512 + DX + 104 + 22, '↑ 召回结果注入 system prompt',
    { size: 11.5, fill: MUTED });

  c.line(SPINE, 497 + DX, SPINE, 645 + DX, { sw: 1.8 });

  // ④ ReAct 循环
  main(645 + DX, 130, ['ReAct 循环（core 主干）', 'LLM 调用 ⇄ tools 执行 ⇄ 结果回流',
                       '每步 tracing 记录 + Langfuse 上报'],
    '#fef3c7', '#d97706');
  c.line(SPINE, 775 + DX, SPINE, 895 + DX, { sw: 1.8 });

  // ⑤ 返回
  main(895 + DX, 74, ['返回回答'], '#e2e8f0', '#64748b');
  c.line(SPINE, 969 + DX, SPINE, 1035 + DX, { sw: 1.8 });

  // ⑥ 记忆时点②（异步）
  main(1035 + DX, 92, ['★ 记忆时点 ②：回答后（后台线程，不阻塞）'],
    '#dcfce7', '#16a34a');
  c.line(SPINE, 1127 + DX, SPINE, 1195 + DX, { sw: 1.8 });
  main(1195 + DX, 104, ['extractor.extract() → memory.add()',
                        '判断值不值得记 → 写入（同样走 embedding_backends）'],
    '#f0fdf4', '#16a34a');

  // 图例
  c.text(40, H - 60, '★ = 记忆被用到的两个时刻：提问前召回注入 / 回答后抽取沉淀',
    { size: 14, weight: 600, fill: INK });
  c.text(40, H - 34, '注：回答后那一步跑在后台线程（core.py 的 threading.Thread）——'
    + '「并发」在本项目里早就存在。', { size: 13, fill: MUTED });

  return wrap(W, H, c.out, 'ai-agent · 运行时数据流（一次对话）',
    '从用户输入到回答，以及记忆被用到的两个时刻');
}

// ---------------------------------------------------------------
const outDir = process.argv[2] || '.';
fs.writeFileSync(`${outDir}/architecture-sketch.svg`, layerDiagram());
fs.writeFileSync(`${outDir}/architecture-flow.svg`, flowDiagram());
console.log('written: architecture-sketch.svg, architecture-flow.svg');
