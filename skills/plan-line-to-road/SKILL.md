---
name: plan-line-to-road
name_zh: 线转道路
description_zh: 业务技能：线转道路（规划应用）。经 YghsBridge MCP 在 ArcMap 内执行。用户提到「线转道路」或同类操作时使用。
user-invocable: true
---

# 线转道路

## 功能
按道路等级和断面宽度，将所选中心线生成道路中心线、路缘石线和道路红线。

## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：
- 输入图层/表（名称或路径）
- 目标字段（若涉及属性写入）
- 关键算法参数（单位/分级/阈值）
- 输出位置（GDB 要素类 / xlsx 路径）
- 坐标系要求：沿用当前工程

**原窗体参数项**（提取自界面定义，作问询参照）：线图层

## 执行路径（ArcMap 版）
本技能经 **yghsBridge ArcMap 桥接**执行：AI 按上方问询清单逐项确认参数后，
把参数代入执行脚本 `scripts/run.py`，经桥的 `execute_code` 通道（py2.7 arcpy）在 ArcMap 内执行。

脚本用法：
```
run.py <中心线图层> <红线宽度米> <路缘石内缩米> <输出GDB> <红线名> <路缘石线名> <中心线名>
```
⚠ 原版为 Pro SDK GeometryEngine 精确几何（线偏移/圆角/交叉口），本脚本为 Buffer 近似降级实现。
执行完成后读回输出行数/抽查字段值/确认成果文件非空。

## 原始实现要点（参考，源自 Pro 版）
**源码**：完整随附于本技能目录——`source/LineToRoad.xaml`、`source/LineToRoad.xaml.cs`、`source/RoadDesignService.cs`

**算法**（原版比"宽度外扩"复杂得多，核心在 RoadDesignService）：
- **等级→断面**：10 个等级各有默认分带（人行道/非机动车道/绿化带/机动车道/中央分隔带，
  左右对称），如 主干道=4+4+2+10.5+0+10.5+2+4+4；快速路中央分隔带 2m；高速 15+4…
- **板型**：一块板/两块板/三块板/四块板（ApplyPlate 按板型归并分带）；
- 转弯半径矩阵（RoadTurnRadiusOptions，按宽度配对 BuildPairKey）用于交叉口圆角；
- 生成模式与图层稳定性守护（RepairManagedRoadLayersAsync）。
桥等效实现（简化）：按等级取断面总宽 W=左右分带之和，中心线两侧偏移红线/路缘石线；
交叉口圆角需额外处理（当前简化为直角）。**完整效果依赖原插件窗体的断面选择**。
