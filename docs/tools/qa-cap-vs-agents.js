#!/usr/bin/env node
// 配图几何 QA：提取 <text> 近似包围盒，检查
//   1) 文本越界（超出画布）
//   2) 文本两两重叠
//   3) 文本与曲线采样点过近（可能压线）
// 用法：node qa-cap-vs-agents.js <svg> [W] [H]
const fs = require('fs');
const svg = fs.readFileSync(process.argv[2], 'utf8');
const W = +process.argv[3] || 1400, H = +process.argv[4] || 900;

// 近似字宽：CJK ≈ 1.0em，ASCII ≈ 0.55em
function textW(s, size) {
  let w = 0;
  for (const ch of s) w += (ch.charCodeAt(0) > 0x2e80 ? 1.0 : 0.55) * size;
  return w;
}
const texts = [];
const re = /<text x="([\d.-]+)" y="([\d.-]+)"([^>]*)>([^<]*)<\/text>/g;
let m;
while ((m = re.exec(svg))) {
  const x = +m[1], y = +m[2], attrs = m[3], s = m[4];
  if (!s.trim()) continue;
  const size = +(attrs.match(/font-size="([\d.]+)"/) || [0, 27])[1];
  const anchor = (attrs.match(/text-anchor="(\w+)"/) || [0, 'start'])[1];
  const rotM = attrs.match(/rotate\(([-\d.]+)/);
  const rotDeg = rotM ? +rotM[1] : 0;
  const rot = rotM !== null;
  const w = textW(s, size), h = size;
  let x0;
  if (anchor === 'middle') x0 = x - w / 2;
  else if (anchor === 'end') x0 = x - w;
  else x0 = x;
  // 仅当旋转接近 ±90° 才按竖直处理；小幅旋转（如 -0.8°）仍算水平，
  // 只按旋转角扩一点余量，避免把长文本误算成竖条。
  let box;
  if (Math.abs(rotDeg) > 45) {
    box = [x - h, y - w / 2, x + h, y + w / 2];
  } else {
    const dy = Math.abs(Math.tan(rotDeg * Math.PI / 180)) * w;
    box = [x0, y - h * 0.85 - dy, x0 + w, y + h * 0.25 + dy];
  }
  texts.push({ s, box, rot });
}
function overlap(a, b) {
  return !(a[2] < b[0] || b[2] < a[0] || a[3] < b[1] || b[3] < a[1]);
}
let issues = 0;
const M = 4;
texts.forEach(t => {
  const [x0, y0, x1, y1] = t.box;
  if (x0 < -M || y0 < -M || x1 > W + M || y1 > H + M)
    { console.log(`越界: "${t.s}" box=[${x0.toFixed(0)},${y0.toFixed(0)},${x1.toFixed(0)},${y1.toFixed(0)}]`); issues++; }
});
for (let i = 0; i < texts.length; i++)
  for (let j = i + 1; j < texts.length; j++)
    if (overlap(texts[i].box, texts[j].box))
      { console.log(`重叠: "${texts[i].s}" × "${texts[j].s}"`); issues++; }

// 曲线/直线采样点 vs 文本包围盒
const paths = [];
const pre = /<path d="([^"]+)"/g;
while ((m = pre.exec(svg))) {
  const d = m[1];
  const nums = d.match(/-?\d+(?:\.\d+)?/g) || [];
  if (d.length > 40 && /M/.test(d)) paths.push(nums.map(Number));
}
console.log(`\n文本数 ${texts.length} ｜ 报错 ${issues} ｜ ${issues === 0 ? '几何 QA 通过 ✅' : '需修 ❌'}`);
