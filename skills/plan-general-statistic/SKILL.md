---
name: plan-general-statistic
name_zh: 通用面积统计
description_zh: 业务技能：通用面积统计（规划应用）。经 YghsBridge MCP 在 ArcMap 内执行。用户提到「通用面积统计」或同类操作时使用。
user-invocable: true
---

# 通用面积统计

## 功能
通用面积统计。

## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：
- 输入图层/表（名称或路径）
- 目标字段（若涉及属性写入）
- 关键算法参数（单位/分级/阈值）
- 输出位置（GDB 要素类 / xlsx 路径）
- 坐标系要求：投影坐标系（米）

**原窗体参数项**（提取自界面定义，作问询参照）：输入设置 ／ 统计图层或表： ／ 统计面积： ／ 参数设置 ／ 面积单位： ／ 小数单位： ／ 输出设置 ／ 输出Excel路径：

**界面固定选项**：平方米 ｜ 公顷 ｜ 平方千米 ｜ 亩 ｜ 不处理 ｜ 1 ｜ 2 ｜ 3 ｜ 4 ｜ 5 ｜ 6

## 执行路径（ArcMap 版）
本技能经 **yghsBridge ArcMap 桥接**执行：AI 按上方问询清单逐项确认参数后，
把参数代入执行脚本 `scripts/run.py`，经桥的 `execute_code` 通道（py2.7 arcpy）在 ArcMap 内执行。

脚本用法：
```
run.py <图层> <面积字段> <分组字段;分隔> <单位> <输出CSV> [小数位]
```

执行完成后读回输出行数/抽查字段值/确认成果文件非空。

## 原始实现要点（参考，源自 Pro 版）
**源码**：完整随附于本技能目录——`source/GeneralStatistic.xaml`、`source/GeneralStatistic.xaml.cs`

**算法**：通用面积统计表（resources/ 已带模板）：
1. 单位系数同上；2. 多统计字段用 `;` 拼接（支持 1~N 个分组字段）；
3. `management.Statistics(statLayer, tem_sta, "{statArea} SUM", statFields)`；
4. 写 Excel：每行 = 分组字段值 + SUM_面积/单位系数 + 占总面积百分比；末行「总面积/100」；
5. Excel 修饰：多字段时合并同值列、设小数位。


**依赖资源**：已复制到本技能 `resources/` 子目录（1 份）。
