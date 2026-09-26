---
name: plan-s-q-s-x-statistics
name_zh: 三线占用情况汇总表
description_zh: 业务技能：三线占用情况汇总表（规划应用）。经 YghsBridge MCP 在 ArcMap 内执行。用户提到「三线占用情况汇总表」或同类操作时使用。
user-invocable: true
---

# 三线占用情况汇总表

## 功能
三线占用情况汇总表。

## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：
- 输入图层/表（名称或路径）
- 目标字段（若涉及属性写入）
- 关键算法参数（单位/分级/阈值）
- 输出位置（GDB 要素类 / xlsx 路径）
- 坐标系要求：沿用当前工程

**原窗体参数项**（提取自界面定义，作问询参照）：选择城镇开发边界： ／ 输出Excel文件路径： ／ 选择分区名称字段： ／ 面积类型： ／ 面积单位： ／ 选择永久基本农田： ／ 选择生态保护红线： ／ 选择分区图层：

## 执行路径（ArcMap 版）
本技能经 **yghsBridge ArcMap 桥接**执行：AI 按上方问询清单逐项确认参数后，
把参数代入执行脚本 `scripts/run.py`，经桥的 `execute_code` 通道（py2.7 arcpy）在 ArcMap 内执行。

脚本用法：
```
run.py <分区图层> <分区字段> <开发边界> <永基农田> <生态红线> <面积类型> <单位> <输出CSV> [扣减系数字段]
```

执行完成后读回输出行数/抽查字段值/确认成果文件非空。

## 原始实现要点（参考，源自 Pro 版）
**源码**：完整随附于本技能目录——`source/SQSXStatistics.xaml`、`source/SQSXStatistics.xaml.cs`

**算法**（三区三线 vs 分区）：对 开发边界/永基农田/生态红线 三个图层逐个：
1. `analysis.Clip(item, zone)` → `analysis.Identity(clip, zone)` → 加 mj_sx；
2. 面积：投影=`!shape.area!`，椭球=`!shape.geodesicarea!`；**永基农田要乘扣减系数**：
   `!shape.area!*(1-!KCXS!)`（KCXS 为基本农田图层的扣减系数字段）；
3. `management.Statistics(out_zone, out_table, "mj_sx SUM", mcField)`（按分区名字段分组）；
4. 写模板【模板】三区三线指标汇总表.xlsx：按分区名复制行，三线分别写 2/3/4 列，加合计行，改单位标注。


**依赖资源**：已复制到本技能 `resources/` 子目录（1 份）。
