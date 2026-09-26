---
name: plan-create-road-intersection
name_zh: 生成道路交叉口
description_zh: 业务技能：生成道路交叉口（规划应用）。经 YghsBridge MCP 在 ArcMap 内执行。用户提到「生成道路交叉口」或同类操作时使用。
user-invocable: true
---

# 生成道路交叉口

## 功能
基于道路中心线和断面参数，生成带交叉口转角的道路中心线、路缘石线和道路红线。

## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：
- 输入图层/表（名称或路径）
- 目标字段（若涉及属性写入）
- 关键算法参数（单位/分级/阈值）
- 输出位置（GDB 要素类 / xlsx 路径）
- 坐标系要求：沿用当前工程

**原窗体参数项**（提取自界面定义，作问询参照）：

## 执行路径（ArcMap 版）
本技能经 **yghsBridge ArcMap 桥接**执行：AI 按上方问询清单逐项确认参数后，
把参数代入执行脚本 `scripts/run.py`，经桥的 `execute_code` 通道（py2.7 arcpy）在 ArcMap 内执行。

脚本用法：
```
run.py <道路中心线图层> <输出GDB> <输出要素类名>
```
⚠ 原版为 Pro SDK 精确几何（交点打断/转弯半径圆角），本脚本为 Intersect 交点近似降级实现。
执行完成后读回输出行数/抽查字段值/确认成果文件非空。

## 原始实现要点（参考，源自 Pro 版）
**源码**：完整随附于本技能目录——`source/CreateRoadIntersection.xaml`、`source/CreateRoadIntersection.xaml.cs`、`source/RoadDesignService.cs`

**算法**：基于已生成的道路线做交叉口处理——按 activeTurnRadiusOptions（转弯半径矩阵，
按相交道路宽度配对 BuildPairKey(firstWidth, secondWidth) 查半径）在相交处做圆角/打断，
重新生成 中心线/路缘石线/红线 三层。桥等效：Intersect 求交点 → 按两路宽度查半径 →
几何圆角（buffer + boundary 截取）。原版细节在 RoadDesignService.CreateRoadIntersection。
