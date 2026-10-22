# 5 个可视化 Demo · 来源与做法

| # | Demo | Skill | 用到的部分 |
|---|---|---|---|
| 1 | 成本结构图 | [antvis/chart-visualization-skills](https://github.com/antvis/chart-visualization-skills) | 26+ 图表选择、G2 风格、KPI/注释式布局 |
| 2 | Agent Loop 结构图 | [coleam00/excalidraw-diagram-skill](https://github.com/coleam00/excalidraw-diagram-skill) | hand-drawn 形状、语义箭头、视觉配色 |
| 3 | 开发任务时序图 | [markdown-viewer/skills](https://github.com/markdown-viewer/skills) | Mermaid sequence + 文档型图表 |
| 4 | 数据流引擎 | [wheresryan22/anatomy](https://github.com/wheresryan22/anatomy) | isometric 技术插画、部件/管线/标注 |
| 5 | 暗黑数据视频 | [sixwei2025/dark-infographic-video-skill](https://github.com/sixwei2025/dark-infographic-video-skill) | 深黑 + 橙红光晕、数字滚动、卡片/柱状/JSON 动画 |

## 说明

这一版是把上述 skill 的 `SKILL.md` / README 中的视觉规范抽出来，做成可直接打开、可检查的 demo：

- 1–4 是 SVG，保留源文件，可直接改文字/配色；
- 3 额外保留真实 `sequence.mmd`；
- 5 是 Python/Pillow 渲染 + ffmpeg 编码的 6 秒 MP4；
- 没有依赖付费素材或外部 CDN；
- 数据来自 `visualizer/trace_dev.jsonl` 的真实开发 trace。

## 重新生成

```bash
python3 visual-demos/build_visuals.py   # 1-4 SVG
python3 visual-demos/make_previews.py   # 1-4 方形预览 PNG
python3 visual-demos/build_video.py     # 5 MP4 + cover
open visual-demos/index.html
```
