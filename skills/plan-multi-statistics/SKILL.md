---
name: plan-multi-statistics
name_zh: 智能汇总统计
description_zh: 业务技能：智能汇总统计（规划应用）。经 YghsBridge MCP 在 ArcMap 内执行。用户提到「智能汇总统计」或同类操作时使用。
user-invocable: true
---

# 智能汇总统计

## 功能
智能汇总统计。

## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：
- 输入图层/表（名称或路径）
- 目标字段（若涉及属性写入）
- 关键算法参数（单位/分级/阈值）
- 输出位置（GDB 要素类 / xlsx 路径）
- 坐标系要求：沿用当前工程

**原窗体参数项**（提取自界面定义，作问询参照）：分区图层： ／ 分区字段： ／ 输出结果文件夹： ／ 面积类型： ／ 面积单位： ／ 小数位数： ／ 待统计图层 ／ 字段1 ／ 字段2 ／ 字段3 ／ 字段4

## 执行路径（ArcMap 版）
本技能经 **yghsBridge ArcMap 桥接**执行：AI 按上方问询清单逐项确认参数后，
把参数代入执行脚本 `scripts/run.py`，经桥的 `execute_code` 通道（py2.7 arcpy）在 ArcMap 内执行。

脚本用法：
```
run.py <分区图层> <分区字段> <面积类型:投影|椭球> <单位> <输出CSV> <图层1> [图层2...]
```

执行完成后读回输出行数/抽查字段值/确认成果文件非空。

## 原始实现要点（参考，源自 Pro 版）
**源码**：完整随附于本技能目录——`source/MultiStatistics.xaml`、`source/MultiStatistics.xaml.cs`

**算法**（参照范围 zoom 与 N 个待统计图层的相交统计）：
1. 输出文件夹建「临时数据库.gdb」；复制 zoom → defGDB\zoom；复制模板智能统计表.xlsx；
2. 对每个待统计图层：`analysis.Intersect([ly, zoom])` → 加 BJMJ 字段
   （area_type=椭球 → `!shape.geodesicarea!`，否则 `!shape.area!`）→
   `management.Statistics(intersect, statistics, "BJMJ SUM", allFields)`（allFields=参照字段+本图层字段，防重名）→ 写 Excel；
3. 单独一份只按本图层字段的汇总（statistics_fd）；
4. 最后删除参照行列。


**依赖资源**：已复制到本技能 `resources/` 子目录（1 份）。
