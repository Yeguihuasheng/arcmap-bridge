---
name: plan-supply0-d-m
name_zh: 用地代码后补充0
description_zh: 业务技能：用地代码后补充0（规划应用）。经 YghsBridge MCP 在 ArcMap 内执行。用户提到「用地代码后补充0」或同类操作时使用。
user-invocable: true
---

# 用地代码后补充0

## 功能
用地代码后补充0。

## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：
- 输入图层/表（名称或路径）
- 目标字段（若涉及属性写入）
- 关键算法参数（单位/分级/阈值）
- 输出位置（GDB 要素类 / xlsx 路径）
- 坐标系要求：沿用当前工程

**原窗体参数项**（提取自界面定义，作问询参照）：选择图层或表： ／ 选择用地代码字段： ／ 补齐至文本长度：

**默认值**：txtLength 默认=6

## 执行路径（ArcMap 版）
本技能经 **yghsBridge ArcMap 桥接**执行：AI 按上方问询清单逐项确认参数后，
把参数代入执行脚本 `scripts/run.py`，经桥的 `execute_code` 通道（py2.7 arcpy）在 ArcMap 内执行。

脚本用法：
```
run.py <图层> <字段名> <目标位数LEN>
```

执行完成后读回输出行数/抽查字段值/确认成果文件非空。

## 原始实现要点（参考，源自 Pro 版）
**源码**：完整随附于本技能目录——`source/Supply0DM.xaml`、`source/Supply0DM.xaml.cs`

**算法**：`CalculateField(fc, field, "!field!.ljust(LEN, '0')")`——把用地代码用 0 **右填充**到指定
位数 LEN（LEN 由用户在窗体里设定）。与 remove0-d-m 互为逆操作。执行前须问询 LEN。
