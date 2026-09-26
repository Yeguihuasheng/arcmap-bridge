---
name: plan-y-d-y-h-old2-new
name_zh: 用地用海旧转新
description_zh: 业务技能：用地用海旧转新（规划应用）。经 YghsBridge MCP 在 ArcMap 内执行。用户提到「用地用海旧转新」或同类操作时使用。
user-invocable: true
---

# 用地用海旧转新

## 功能
用地用海旧转新。

## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：
- 输入图层/表（名称或路径）
- 目标字段（若涉及属性写入）
- 关键算法参数（单位/分级/阈值）
- 输出位置（GDB 要素类 / xlsx 路径）
- 坐标系要求：沿用当前工程

**原窗体参数项**（提取自界面定义，作问询参照）：选择用地用海图层： ／ 选择旧编码： ／ 输出新编码： ／ 输出新名称(可选)：

## 执行路径（ArcMap 版）
本技能经 **yghsBridge ArcMap 桥接**执行：AI 按上方问询清单逐项确认参数后，
把参数代入执行脚本 `scripts/run.py`，经桥的 `execute_code` 通道（py2.7 arcpy）在 ArcMap 内执行。

脚本用法：
```
run.py <图层> <旧编码字段oldBM> <新编码字段newBM> <新名称字段newMC>
```

执行完成后读回输出行数/抽查字段值/确认成果文件非空。

## 原始实现要点（参考，源自 Pro 版）
**源码**：完整随附于本技能目录——`source/YDYHOld2New.xaml`、`source/YDYHOld2New.xaml.cs`

**算法**：旧用地用海编码 → 新编码 → 新名称，**两步级联映射**（resources/ 内两份表）：
1. CheckData(fc, oldBM)；
2. 复制 旧用地用海编码_to_新用地用海编码.xlsx → AttributeMapper(fc, oldBM, newBM, sheet1$)；
3. 复制 新版用地用海_DM_to_MC.xlsx → AttributeMapper(fc, newBM, newMC, sheet1$)。


**依赖资源**：已复制到本技能 `resources/` 子目录（2 份）。
