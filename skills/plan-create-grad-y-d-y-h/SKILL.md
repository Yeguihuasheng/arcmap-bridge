---
name: plan-create-grad-y-d-y-h
name_zh: 生成分级用地用海编码名称
description_zh: 业务技能：生成分级用地用海编码名称（规划应用）。经 YghsBridge MCP 在 ArcMap 内执行。用户提到「生成分级用地用海编码名称」或同类操作时使用。
user-invocable: true
---

# 生成分级用地用海编码名称

## 功能
生成分级用地用海编码名称。

## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：
- 输入图层/表（名称或路径）
- 目标字段（若涉及属性写入）
- 关键算法参数（单位/分级/阈值）
- 输出位置（GDB 要素类 / xlsx 路径）
- 坐标系要求：沿用当前工程

**原窗体参数项**（提取自界面定义，作问询参照）：输入要素图层： ／ 输入用地用海编码字段： ／ 用地用海分级： ／ 用地用海版本：

## 执行路径（ArcMap 版）
本技能经 **yghsBridge ArcMap 桥接**执行：AI 按上方问询清单逐项确认参数后，
把参数代入执行脚本 `scripts/run.py`，经桥的 `execute_code` 通道（py2.7 arcpy）在 ArcMap 内执行。

脚本用法：
```
run.py <图层> <编码字段BM> <分级数1|2|3> <版本:旧版|新版> <是否生成名称:是|否>
```

执行完成后读回输出行数/抽查字段值/确认成果文件非空。

## 原始实现要点（参考，源自 Pro 版）
**源码**：完整随附于本技能目录——`source/CreateGradYDYH.xaml`、`source/CreateGradYDYH.xaml.cs`

**算法**：从完整用地用海编码派生分级编码/名称（model=分级数 1~3，isMC=是否同时出名称）：
1. 选表：旧版→用地用海_DM_to_MC.xlsx；新版→新版用地用海_DM_to_MC.xlsx（sheet1=编码→名称）；
2. model≥1：AddField BM_1 → CalculateField `!bmField![:2]`（大类=前2位）；isMC 时 BM_1 查表得 MC_1；
3. model≥2：BM_2 → 代码块 `if len(a)>2: return a[:4] else: ""`（中类=前4位）；isMC 查表得 MC_2；
4. model≥3：BM_3 → `if len(a)>4: return a[:6] else: ""`（小类=前6位）；isMC 查表得 MC_3。
（resources/ 已带两版码表）


**依赖资源**：已复制到本技能 `resources/` 子目录（2 份）。
