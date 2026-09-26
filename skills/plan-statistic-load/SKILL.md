---
name: plan-statistic-load
name_zh: 统计道路网密度
description_zh: 业务技能：统计道路网密度（规划应用）。经 YghsBridge MCP 在 ArcMap 内执行。用户提到「统计道路网密度」或同类操作时使用。
user-invocable: true
---

# 统计道路网密度

## 功能
统计道路网密度。

## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：
- 输入图层/表（名称或路径）
- 目标字段（若涉及属性写入）
- 关键算法参数（单位/分级/阈值）
- 输出位置（GDB 要素类 / xlsx 路径）
- 坐标系要求：沿用当前工程

**原窗体参数项**（提取自界面定义，作问询参照）：道路图层： ／ 道路类型： ／ 范围图层： ／ 输出Excel：

## 执行路径（ArcMap 版）
本技能经 **yghsBridge ArcMap 桥接**执行：AI 按上方问询清单逐项确认参数后，
把参数代入执行脚本 `scripts/run.py`，经桥的 `execute_code` 通道（py2.7 arcpy）在 ArcMap 内执行。

脚本用法：
```
run.py <道路线图层> <道路类型字段> <范围面图层> <输出CSV>
```

执行完成后读回输出行数/抽查字段值/确认成果文件非空。

## 原始实现要点（参考，源自 Pro 版）
**源码**：完整随附于本技能目录——`source/StatisticLoad.xaml`、`source/StatisticLoad.xaml.cs`

**算法**（道路网密度）：
1. `analysis.Clip(roadLy, polygonLy, clipFc)`（范围内道路）；
2. `management.Statistics(clipFc, statTable, "Shape_Length SUM", roadTypeField)`（按道路类型求长度和）；
3. 排序序：铁路→高速公路→快速路→主干路→次干路→支路→其它；
4. 写模板道路统计.xlsx：序号/类型/长度(km=米/1000)/路网密度(km/km²=长度/范围面积×1000)，加合计行；
5. 清理 clipFc 与 statTable。


**依赖资源**：已复制到本技能 `resources/` 子目录（1 份）。
