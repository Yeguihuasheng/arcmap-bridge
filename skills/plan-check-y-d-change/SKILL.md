---
name: plan-check-y-d-change
name_zh: 检查现状规划用地变化
description_zh: 业务技能：检查现状规划用地变化（规划应用）。经 YghsBridge MCP 在 ArcMap 内执行。用户提到「检查现状规划用地变化」或同类操作时使用。
user-invocable: true
---

# 检查现状规划用地变化

## 功能
检查现状规划用地变化。

## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：
- 输入图层/表（名称或路径）
- 目标字段（若涉及属性写入）
- 关键算法参数（单位/分级/阈值）
- 输出位置（GDB 要素类 / xlsx 路径）
- 坐标系要求：沿用当前工程

**原窗体参数项**（提取自界面定义，作问询参照）：输入现状用地图层： ／ 输入现状用地检查字段(编码或名称)： ／ 输入规划用地图层： ／ 输入规划用地检查字段(编码或名称)：

## 执行路径（ArcMap 版）
本技能经 **yghsBridge ArcMap 桥接**执行：AI 按上方问询清单逐项确认参数后，
把参数代入执行脚本 `scripts/run.py`，经桥的 `execute_code` 通道（py2.7 arcpy）在 ArcMap 内执行。

脚本用法：
```
run.py <现状图层> <规划图层> <现状字段> <规划字段> <输出要素类>
```

执行完成后读回输出行数/抽查字段值/确认成果文件非空。

## 原始实现要点（参考，源自 Pro 版）
**源码**：完整随附于本技能目录——`source/CheckYDChange.xaml`、`source/CheckYDChange.xaml.cs`

**算法**（现状 vs 规划 变化检测，输入为两个 TXT 转来的要素）：
1. CheckData(fc_xz_txt, fc_gh_txt)（含重叠告警）；
2. CopyFeatures 两输入到默认 GDB 临时层 tem_xz / tem_gh；
3. AlterField 分别把检查字段改名为「现状_字段名」「规划_字段名」；
4. `analysis.Identity(tem_xz, tem_gh, identityFeatureClass)`（现状为 target，规划做 identity）；
5. 加变化字段 field_change，逐行比较：现状值 ≠ 规划值 → 写「【现状值】-->【规划值】」；
6. Select(field_change IS NOT NULL) 输出 checkRezult；
7. 删除中间层，DeleteField(method=KEEP_FIELDS) 只留有用字段。
