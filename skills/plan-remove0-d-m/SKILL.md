---
name: plan-remove0-d-m
name_zh: 移除用地代码后的0
description_zh: 业务技能：移除用地代码后的0（规划应用）。经 YghsBridge MCP 在 ArcMap 内执行。用户提到「移除用地代码后的0」或同类操作时使用。
user-invocable: true
---

# 移除用地代码后的0

## 功能
移除用地代码后的0。

## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：
- 输入图层/表（名称或路径）
- 目标字段（若涉及属性写入）
- 关键算法参数（单位/分级/阈值）
- 输出位置（GDB 要素类 / xlsx 路径）
- 坐标系要求：沿用当前工程

**原窗体参数项**（提取自界面定义，作问询参照）：选择图层或表： ／ 选择用地代码字段：

## 执行路径（ArcMap 版）
本技能经 **yghsBridge ArcMap 桥接**执行：AI 按上方问询清单逐项确认参数后，
把参数代入执行脚本 `scripts/run.py`，经桥的 `execute_code` 通道（py2.7 arcpy）在 ArcMap 内执行。

脚本用法：
```
run.py <图层> <字段名>
```

执行完成后读回输出行数/抽查字段值/确认成果文件非空。

## 原始实现要点（参考，源自 Pro 版）
**源码**：完整随附于本技能目录——`source/Remove0DM.xaml`、`source/Remove0DM.xaml.cs`

**算法（原版代码块，逐字保留）**：对指定文本字段做 CalculateField，代码块：

```python
def ss(a):
    if a[2:] == '0'*(len(a)-2):
        return a[:2]
    elif a[4:] == '0'*(len(a)-4):
        return a[:4]
    else:
        return a
```

语义：用地代码只保留 **2 位大类** 或 **4 位中类** 主干，砍掉其后的补位 0。
注意：不是简单 rstrip('0')——长度为 3 的 "100" 会得到 "10"（rstrip 会错成 "1"）。
GP 调用：`management.CalculateField(fc, field, "ss(!field!)", codeblock)`。
