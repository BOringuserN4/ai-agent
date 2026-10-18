---
name: hand-drawn-diagram
description: 生成 Notability/Excalidraw 手绘风教学插图（SVG + PNG），复用项目现有的 roughjs 基元与 @resvg 渲染；适合概念图、架构图、流程图、对比图。
whenToUse: 当教学文档需要插图，且要求手绘/笔记风格时。
---

# 手绘风插图工作流

> 项目里已有一套可复用的手绘生成器：
> `docs/tools/gen-notability.js`（基元）、`docs/tools/gen-teaching-figures.js`（教学图）、
> `docs/tools/gen-arch-all.js`（架构总览）。本 skill 把“怎么画、怎么验”固化下来。

## 0. 先写一句“这张图要说什么”

一张图只讲**一件事**。先写下：

> 这张图要让读者记住：____________________。

如果一句话说不清，说明该拆成两张图。

## 1. 风格规格（跟着项目走）

| 项 | 规格 |
|---|---|
| 底材 | 米白纸 `#fbf7ef` + 点阵网格 + 轻微噪点/暗角 |
| 笔触 | 双层手绘描边（主笔 2.4–3px + 副笔 1.2–1.6px@0.3） |
| 箭头 | 二次贝塞尔弓形 + 双短线箭头；异步用虚线 |
| 色块 | 马克笔半透明色块，轻微旋转；不要纯色填充 |
| 字体 | `ZCOOL KuaiLe` / `PingFang SC`；中文为主，英文只做副标 |
| 画幅 | 教学图 1400×900 / 1600×1050 / 1600×860；导出 2× |
| 颜色语义 | 蓝=输入/用户，橙=LLM/决策，绿=工具/执行，紫=记忆/数据，粉=质量/评审 |

## 2. 生成流程

1. **选模板**
   - 教学概念图：复制 `docs/tools/gen-teaching-figures.js` 的结构。
   - 架构图：`gen-notability.js`。
   - 总览/数据流：`gen-arch-all.js`。
2. **复用基元**（不要重写）：
   `jline` / `handRect` / `handEllipse` / `handArrow` / `markerBlock` /
   `txt` / `wavyUnderline` / `star` / `defs` / `wrap`。
3. **布局**
   - 标题 46px；模块标题 20–28px；注释 13–16px。
   - 主盒子 ≤ 7 个；留白 ≥ 40px；箭头不穿字。
   - 注释放在盒子外侧，别塞进边框。
4. **生成**
   ```bash
   node docs/tools/gen-teaching-figures.js
   ```
   输出：`docs/diagrams/<name>.svg` + `.png`。
5. **渲染 PNG**
   - 用 `@resvg/resvg-js`（项目已装），宽度 2200–2400。
   - **不要用 `qlmanage`**：宽图会被裁切（项目踩过坑）。
6. **QA（必须做）**
   - 用 `read_image` 看 PNG；
   - 查：文字压框 / 箭头穿字 / 标签重叠 / 画幅裁切 / 字号过大；
   - 修完重新生成，再看一遍。
7. **嵌入文档**
   ```markdown
   ![图 1｜Agent 的本质](../diagrams/教学-Agent本质.png)

   > 图 1｜一个循环 + 一份工具清单；其余都是加在它上面的成本。
   ```
   图后必须有一段“看图说话”。

## 3. 布局检查清单

- [ ] 一张图只讲一件事
- [ ] 主盒子 ≤ 7 个
- [ ] 标题/副标/图注齐全
- [ ] 文字不压框、不穿箭头
- [ ] 箭头方向与语义一致（同步实线 / 异步虚线）
- [ ] 颜色语义没混用
- [ ] PNG 不是从 SVG 裁切出来的
- [ ] 文档里有“看图说话”，不是只丢图

## 4. 反模式

- 把整篇文档塞进一张图（读者会放弃）。
- 用纯色/渐变/阴影，失去手绘感。
- 为了“好看”加无关装饰，挤掉信息。
- 只生成 SVG，不检查 PNG。
- 用 `qlmanage` 渲染宽图（会被裁切）。
- 图注写“如下图所示”，没有一句人话解释。

## 5. 产物位置

- 源图：`docs/diagrams/*.svg`
- 预览：`docs/diagrams/*.png`
- 生成器：`docs/tools/gen-*.js`
- 教学文档里用相对路径 `../diagrams/xxx.png` 引用。
