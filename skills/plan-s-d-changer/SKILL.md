---
name: plan-s-d-changer
name_zh: 三调DLBM和DLMC转换
description_zh: 业务技能：三调DLBM和DLMC转换（规划应用）。经 YghsBridge MCP 在 ArcMap 内执行。用户提到「三调DLBM和DLMC转换」或同类操作时使用。
user-invocable: true
---

# 三调DLBM和DLMC转换

## 功能
三调DLBM和DLMC转换。

## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：
- 输入图层/表（名称或路径）
- 目标字段（若涉及属性写入）
- 关键算法参数（单位/分级/阈值）
- 输出位置（GDB 要素类 / xlsx 路径）
- 坐标系要求：沿用当前工程

**原窗体参数项**（提取自界面定义，作问询参照）：选择三调图层： ／ DLBM字段： ／ DLMC字段： ／ 转换模式：

## 执行路径（ArcMap 版）
本技能经 **yghsBridge ArcMap 桥接**执行：AI 按上方问询清单逐项确认参数后，
把参数代入执行脚本 `scripts/run.py`，经桥的 `execute_code` 通道（py2.7 arcpy）在 ArcMap 内执行。

脚本用法：
```
run.py <图层> <DLBM字段> <DLMC字段> <模式:DLBM转DLMC|DLMC转DLBM>
```

执行完成后读回输出行数/抽查字段值/确认成果文件非空。

## 原始实现要点（参考，源自 Pro 版）
**源码**：完整随附于本技能目录——`source/SDChanger.xaml`、`source/SDChanger.xaml.cs`

**算法**：三调地类编码↔名称互转，靠**映射表 Excel**（资源：`resources/三调BM_MC.xlsx`）：
1. 复制 resources/三调BM_MC.xlsx 到工程 Home 文件夹；
2. 模式「DLBM转DLMC」→ 用 sheet1$（编码→名称）做属性映射；「DLMC转DLBM」→ 用 sheet2$；
3. 属性映射 = 对目标字段逐行查表替换（可经桥用 CalculateField+字典 或 SearchCursor+UpdateCursor 实现）；
4. 完成后删除临时 xlsx。
执行前 CheckData 会校验：图层存在、DLBM/DLMC 字段存在、代码格式合法（不合法直接报错返回）。


**依赖资源**：已复制到本技能 `resources/` 子目录（1 份）。
