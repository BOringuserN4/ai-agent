#!/usr/bin/env node
// 几何 QA（skill step 6）：用算术断言，不靠 vision
const fs = require('fs');

const W = 2760, H = 1820;
const COLW = 396, COLGAP = 42;
const ROOT_W = 430, ROOT_H = 92, ROOT_Y = 150;
const BUS_Y = 292, HEAD_Y = 336, HEAD_H = 70;
const CARD_Y0 = 442, CARD_H = 172, CARD_STEP = 190;
const NCOL = 6;
const maxLeaves = 6;   // 编排章

const colX = i => { const total = NCOL*COLW + (NCOL-1)*COLGAP; const m=(W-total)/2; return m + i*(COLW+COLGAP); };

let fail = 0;
const chk = (name, cond, detail='') => {
  console.log(`${cond ? '✅' : '❌'} ${name}${detail ? '  — ' + detail : ''}`);
  if (!cond) fail++;
};

// 1. 列不重叠、不越界
let okCols = true, detail = [];
for (let i=0;i<NCOL;i++){
  const x0 = colX(i), x1 = x0+COLW;
  if (x0 < 0 || x1 > W) { okCols=false; detail.push(`col${i} 越界 ${x0}..${x1}`); }
  if (i>0){ const pg = colX(i-1)+COLW; if (x0 - pg < 20){ okCols=false; detail.push(`col${i-1}->${i} 间隙 ${(x0-pg).toFixed(0)}px`);} }
}
chk('列不重叠且不越界', okCols, detail.join('; '));

// 2. 根节点居中
const cxRoot = W/2;
const c0 = colX(0)+COLW/2, cN = colX(NCOL-1)+COLW/2;
chk('根/总线居中', Math.abs((c0+cN)/2 - cxRoot) < 1, `总线中心 ${((c0+cN)/2).toFixed(1)} vs 画幅中心 ${cxRoot}`);

// 3. 垂直堆叠不越界（最高列）
const maxBottom = CARD_Y0 + (maxLeaves-1)*CARD_STEP + CARD_H;
chk('最高列卡片不越底', maxBottom < H, `最高列底 ${maxBottom} < 画布高 ${H}`);
chk('卡片区在列头之下', CARD_Y0 > HEAD_Y+HEAD_H, `${CARD_Y0} > ${HEAD_Y+HEAD_H}`);
chk('总线在根之下、列头之上', ROOT_Y+ROOT_H < BUS_Y && BUS_Y < HEAD_Y, `${ROOT_Y+ROOT_H} < ${BUS_Y} < ${HEAD_Y}`);

// 4. 卡片内文本宽度估算（CJK 1em，latin 0.55em）不越卡片右缘
function estWidth(s, size){
  let w=0; for (const ch of s){ w += (ch.charCodeAt(0) > 0x2E80 ? 1.0 : 0.55) * size; } return w;
}
const texts = [
  ['system 定人格与输出格式',15], ['协议化工具调用（N+M）',15], ['88 行纯 ReAct 循环',15],
  ['N 框架 × M 工具 = N×M 适配',15], ['指令不清 → 输出全飘',15], ['先做到「一口气读完」',15],
  ['意图分类 → 分派专家',15], ['跨域 ≠ 该拆，默认 solo',15],
  ['固定顺序串联，前出=后入',15], ['线性流程最省心',15],
  ['并行分发 + 汇聚',15], ['独立且资源可吸收 → 省 41%',15],
  ['生成 → 批判 → 重做',15], ['自己批自己 = 自我确认',15],
  ['先规划，再执行',15], ['实测否决：小任务无病',15],
  ['层级 / 工人池（条件性）',15], ['慢工具省 61–76%，快工具纯负债',15],
  ['外置向量库，按需注入',15], ['召回断层 → 文本增富修',15],
  ['抽取补最近 3 轮上下文',15], ['消解「它」指代（0/2 → 2/2）',15],
  ['Ollama 可插拔后端',15], ['延迟 81ms vs 云端 158ms',15],
  ['Tracer + Langfuse + judge',15], ['黑盒 → 知道「对不对」',15],
  ['工具裁剪 / 预筛 / 清声明',15], ['省 42% / 25% / 59%',15],
  ['截断 + 预算预警 + 收尾步',15], ['软提示压不过惯性 → 撤工具',15],
  ['分层结构 + 运行时数据流',15], ['讲清「为什么这么设计」',15],
  ['项目主线收口',15], ['回路一层层闭合',15],
];
let okText = true, td=[];
for (const [s,size] of texts){
  const w = estWidth(s, size);
  const rightEdgeInCard = 82 + w;   // 文本从 x+82 起
  if (rightEdgeInCard > COLW - 10){ okText=false; td.push(`"${s}" 估宽 ${w.toFixed(0)} → 右缘 x+${rightEdgeInCard.toFixed(0)} > ${COLW-10}`); }
}
chk('卡片内文本不越右缘', okText, td.join('; '));

// 5. 卡片名字不越
let okName = true, nd=[];
for (const s of ['Prompt 工程','工具 · 协议 MCP','最小 Agent（阶梯 0）','Router 路由','Pipeline 流水线','Fan-out 并行','Evaluator-Critic','Planner-Executor','Hierarchical 层级','记忆工程','记忆切分粒度','本地推理','评测 + 可观测','成本优化','资源感知','架构图','学习总结','感知 - 行动结构化','去中心化协商','Group Chat / Blackboard','Contract Net / Debate','LangGraph 官方文档']){
  const w = estWidth(s,20);
  if (18 + w > COLW - 14){ okName=false; nd.push(`"${s}" 估宽 ${w.toFixed(0)}`); }
}
chk('卡片标题不越右缘', okName, nd.join('; '));

// 6. 图例/注记不与卡片列重叠（图例在左下、最高列在右侧，需查 y 区间）
const legendY = 1660;
const colBlocks = [];
for (let i=0;i<NCOL;i++){
  const x0=colX(i), x1=x0+COLW;
  colBlocks.push({i,x0,x1, yTop:HEAD_Y, yBot: CARD_Y0 + (maxLeaves-1)*CARD_STEP + CARD_H});
}
// 图例 x 74..700, y ~1638..1680（列 0 的卡片底只到 994）
const legendBottom = legendY + 40;
let okLegend = true, ld=[];
for (const b of colBlocks){
  const xOverlap = !(700 < b.x0 || 74 > b.x1);
  const yOverlap = !(legendBottom < b.yTop || (legendY-30) > b.yBot);
  if (xOverlap && yOverlap){ okLegend=false; ld.push(`col${b.i} (x${b.x0}..${b.x1}, y${b.yTop}..${b.yBot})`); }
}
chk('图例不与卡片列重叠', okLegend, ld.join('; '));

// 7. 装饰星不压根节点
const rootX0 = W/2-ROOT_W/2, rootX1 = W/2+ROOT_W/2;
const stars = [[760,176],[2100,158],[70,1560]];
let okStar = true, sd=[];
for (const [sx,sy] of stars){
  const inRoot = sx>rootX0-14 && sx<rootX1+14 && sy>ROOT_Y-14 && sy<ROOT_Y+ROOT_H+14;
  if (inRoot){ okStar=false; sd.push(`星(${sx},${sy}) 压根框`); }
}
chk('装饰星不压根节点', okStar, sd.join('; '));

console.log(`\n${fail===0 ? '🎉 几何 QA 全部通过' : '⚠️ '+fail+' 项需修正'}`);
process.exit(fail===0?0:1);
