---
name: plan-batch-map-export
name_zh: 批量出图（布局导出图片）
description: 把一个工程文件里的布局批量导出成图片或 PDF。Pro 走 arcpy.mp 逐个布局导出，ArcMap 走 arcpy.mapping 导出地图文档布局视图。适合村庄规划成果里「现状图 / 规划图 / 管控图」成套出图的重复劳动。
description_zh: 把一个工程文件里的布局批量导出成图片或 PDF。Pro 走 arcpy.mp 逐个布局导出，ArcMap 走 arcpy.mapping 导出地图文档布局视图。适合村庄规划成果里「现状图 / 规划图 / 管控图」成套出图的重复劳动。
argument-hint: <工程文件（Pro 为 .aprx，ArcMap 为 .mxd）> <输出文件夹> <格式（PNG / PDF / JPEG）> <DPI（默认 96）>
user-invocable: true
---

# 批量出图（布局导出图片）

## 功能
把一个工程文件里的布局批量导出成图片或 PDF。Pro 走 arcpy.mp 逐个布局导出，ArcMap 走 arcpy.mapping 导出地图文档布局视图。适合村庄规划成果里「现状图 / 规划图 / 管控图」成套出图的重复劳动。

## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：
- 工程文件（Pro 为 .aprx，ArcMap 为 .mxd）
- 输出文件夹
- 格式（PNG / PDF / JPEG）
- DPI（默认 96）
- 输出位置（GDB 要素类 / csv 路径）
- 坐标系要求：涉及面积时必须确认是否为投影坐标系（脚本已自动按坐标系切换测地面积）

## 执行路径
直接执行本技能的 `scripts/run.py`（参数按顺序传入）。运行环境：ArcMap

## 执行后复核
- 读回输出图层行数/字段值或打开结果表抽查 3 项与预期一致；
- 报出的「待人工细分」「问题清单」必须原样反馈给用户，不要自行取舍。

## 参数与调用
```bat
python scripts\run.py <工程文件（Pro 为 .aprx，ArcMap 为 .mxd）> <输出文件夹> <格式（PNG / PDF / JPEG）> <DPI（默认 96）>
```

## 来源
来自公开开源工具箱的业务口径整理，按业务口径重写为自包含脚本；
原始出处与许可证见 `ATTRIBUTION.md`。
