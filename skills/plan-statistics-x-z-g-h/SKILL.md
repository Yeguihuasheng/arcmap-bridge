---
name: plan-statistics-x-z-g-h
name_zh: 用地用海现状规划指标汇总
description_zh: 业务技能：用地用海现状规划指标汇总（规划应用）。经 YghsBridge MCP 在 ArcMap 内执行。用户提到「用地用海现状规划指标汇总」或同类操作时使用。
user-invocable: true
---

# 用地用海现状规划指标汇总

## 功能
用地用海现状规划指标汇总。

## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：
- 输入图层/表（名称或路径）
- 目标字段（若涉及属性写入）
- 关键算法参数（单位/分级/阈值）
- 输出位置（GDB 要素类 / xlsx 路径）
- 坐标系要求：沿用当前工程

**原窗体参数项**（提取自界面定义，作问询参照）：现状用地： ／ 输出Excel文件路径： ／ 汇总模式： ／ 编码字段： ／ 面积字段： ／ 面积单位： ／ 小数位数： ／ 规划用地： ／ 编码字段： ／ 面积字段：

## 执行路径（ArcMap 版）
本技能经 **yghsBridge ArcMap 桥接**执行：AI 按上方问询清单逐项确认参数后，
把参数代入执行脚本 `scripts/run.py`，经桥的 `execute_code` 通道（py2.7 arcpy）在 ArcMap 内执行。

脚本用法：
```
run.py <现状图层> <规划图层> <编码字段> <面积字段> <单位> <分级> <输出CSV>
```

执行完成后读回输出行数/抽查字段值/确认成果文件非空。

## 原始实现要点（参考，源自 Pro 版）
**源码**：完整随附于本技能目录——`source/StatisticsXZGH.xaml`、`source/StatisticsXZGH.xaml.cs`

**算法**：现状 vs 规划 **双图层** 各自 StatisticsPlus → DecomposeSummary → MergeCodeDict，
然后写入【现状规划】用地用海_{大类|中类|小类}.xlsx 模板（resources/ 已带三份）：
现状值与规划值分列写入（模板里有固定单元格坐标：大类 3/5/7 列、中类 4/6/8、小类 5/7/9），
删除 0 值行与多余列，改单位标注。面积单位系数同 statistics-y-d-y-h。


**依赖资源**：已复制到本技能 `resources/` 子目录（3 份）。
