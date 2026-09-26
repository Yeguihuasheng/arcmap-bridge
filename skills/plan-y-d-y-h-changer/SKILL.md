---
name: plan-y-d-y-h-changer
name_zh: 用地用海转换
description_zh: 业务技能：用地用海转换（规划应用）。经 YghsBridge MCP 在 ArcMap 内执行。用户提到「用地用海转换」或同类操作时使用。
user-invocable: true
---

# 用地用海转换

## 功能
用地用海转换。

## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：
- 输入图层/表（名称或路径）
- 目标字段（若涉及属性写入）
- 关键算法参数（单位/分级/阈值）
- 输出位置（GDB 要素类 / xlsx 路径）
- 坐标系要求：沿用当前工程

**原窗体参数项**（提取自界面定义，作问询参照）：输入要素图层： ／ 输入转换前字段： ／ 输入转换后字段： ／ 转换模式： ／ 用地用海版本：

## 执行路径（ArcMap 版）
本技能经 **yghsBridge ArcMap 桥接**执行：AI 按上方问询清单逐项确认参数后，
把参数代入执行脚本 `scripts/run.py`，经桥的 `execute_code` 通道（py2.7 arcpy）在 ArcMap 内执行。

脚本用法：
```
run.py <图层> <源字段> <目标字段> <模式:代码转名称|名称转代码> <版本:旧版|新版>
```

执行完成后读回输出行数/抽查字段值/确认成果文件非空。

## 原始实现要点（参考，源自 Pro 版）
**源码**：完整随附于本技能目录——`source/YDYHChanger.xaml`、`source/YDYHChanger.xaml.cs`

**算法**：用地用海编码↔名称 互转（与 s-d-changer 同构，但作用于用地用海字段）。
CheckData(model, version, fc_path, field_before, field_after) → ConvertYDYHValue(...)：
按 model（编码转名称/名称转编码）与 version（旧版/新版）选择内置码表做逐行替换。
桥等效：用新版用地用海_DM_to_MC.xlsx（resources 未内置时从 原始工具箱源码 Data/Excel 取）做映射表。
