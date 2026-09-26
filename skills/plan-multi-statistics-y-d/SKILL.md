---
name: plan-multi-statistics-y-d
name_zh: 批量地类面积统计
description_zh: 业务技能：批量地类面积统计（规划应用）。经 YghsBridge MCP 在 ArcMap 内执行。用户提到「批量地类面积统计」或同类操作时使用。
user-invocable: true
---

# 批量地类面积统计

## 功能
批量地类面积统计。

## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：
- 输入图层/表（名称或路径）
- 目标字段（若涉及属性写入）
- 关键算法参数（单位/分级/阈值）
- 输出位置（GDB 要素类 / xlsx 路径）
- 坐标系要求：投影坐标系（米）

**原窗体参数项**（提取自界面定义，作问询参照）：分区图层： ／ 分区字段： ／ 输出结果文件夹： ／ 面积类型： ／ 面积单位： ／ 小数位数： ／ 待统计图层 ／ 地类编码 ／ 地类名称 ／ 扣除系数

## 执行路径（ArcMap 版）
本技能经 **yghsBridge ArcMap 桥接**执行：AI 按上方问询清单逐项确认参数后，
把参数代入执行脚本 `scripts/run.py`，经桥的 `execute_code` 通道（py2.7 arcpy）在 ArcMap 内执行。

脚本用法：
```
run.py <分区图层> <分区字段> <面积类型> <单位> <输出CSV> <图层> <扣除系数字段>
```

执行完成后读回输出行数/抽查字段值/确认成果文件非空。

## 原始实现要点（参考，源自 Pro 版）
**源码**：完整随附于本技能目录——`source/MultiStatisticsYD.xaml`、`source/MultiStatisticsYD.xaml.cs`

**算法**（在 multi-statistics 基础上增加**扣除系数**）：
- lyFields[2] = 扣除系数字段；先 ClearMathNull 防空值；
- BJMJ_OR = shape.area（或椭球）；`BJMJ_EX = BJMJ_OR - BJMJ_OR*扣除系数`；`KCMJ_EX = BJMJ_OR*扣除系数`；
- Statistics 按 "参照字段;lyFields[0];lyFields[1]" 分组，统计 "BJMJ_OR SUM;BJMJ_EX SUM;KCMJ_EX SUM"；
- Excel：初始化列位（sd.InitCol=4+字段数）、逐图层写、清除 0 值列、算合计、设样式。


**依赖资源**：已复制到本技能 `resources/` 子目录（1 份）。
