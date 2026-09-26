---
name: plan-statistics-y-d-y-h
name_zh: 用地用海指标汇总
description_zh: 业务技能：用地用海指标汇总（规划应用）。经 YghsBridge MCP 在 ArcMap 内执行。用户提到「用地用海指标汇总」或同类操作时使用。
user-invocable: true
---

# 用地用海指标汇总

## 功能
用地用海指标汇总。

## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：
- 输入图层/表（名称或路径）
- 目标字段（若涉及属性写入）
- 关键算法参数（单位/分级/阈值）
- 输出位置（GDB 要素类 / xlsx 路径）
- 坐标系要求：沿用当前工程

**原窗体参数项**（提取自界面定义，作问询参照）：输入用地图层： ／ 输出Excel文件路径： ／ 汇总模式： ／ 用地编码字段： ／ 面积字段： ／ 面积单位： ／ 小数位数： ／ 输入分区域图层： ／ 分区字段：

## 执行路径（ArcMap 版）
本技能经 **yghsBridge ArcMap 桥接**执行：AI 按上方问询清单逐项确认参数后，
把参数代入执行脚本 `scripts/run.py`，经桥的 `execute_code` 通道（py2.7 arcpy）在 ArcMap 内执行。

脚本用法：
```
run.py <图层> <编码字段> <面积字段> <单位> <分级:大类|中类|小类> <输出CSV> [分区图层] [分区字段]
```

执行完成后读回输出行数/抽查字段值/确认成果文件非空。

## 原始实现要点（参考，源自 Pro 版）
**源码**：完整随附于本技能目录——`source/StatisticsYDYH.xaml`、`source/StatisticsYDYH.xaml.cs`

**算法**（核心是 ComboTool 三连）：
1. 单位系数：平方米=1、公顷=1e4、平方公里=1e6、亩=666.66667；
2. 复制模板【新模板】用地用海_{大类|中类|小类}.xlsx 到 excel_path（resources/ 已带三份）；
3. 可选**分区域**：对分区图层逐值 Select → Clip(fc, zone) → 对裁剪结果统计；
4. `ComboTool.StatisticsPlus(fc, bmList, areaField, "合计", unit_xs)`——按用地用海编码逐级汇总面积；
5. `DecomposeSummary(dic)` 指标分割、`MergeCodeDict(dic)` 长短编码合并（同一地类的长码/短码归并）；
6. 按模型层级把结果写进模板对应单元格（StatisticsOne/Two/Three）。
桥等效：Statistics GP（按编码分组 SUM 面积）→ Python 端做分割/合并 → 汇报或写 Excel。


**依赖资源**：已复制到本技能 `resources/` 子目录（3 份）。
