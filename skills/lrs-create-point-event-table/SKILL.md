---
name: lrs-create-point-event-table
name_zh: 按间隔生成点事件表
description: 沿路由按固定间隔生成点事件表（路径标识 + 量测值），可直接作为 Locate Features Along Routes 的输入。
description_zh: 沿路由按固定间隔生成点事件表（路径标识 + 量测值），可直接作为 Locate Features Along Routes 的输入。
argument-hint: <输入路由要素（已带 M 值）> <路径标识字段> <生成间隔（默认 10）> <输出事件表>
user-invocable: true
---

# 按间隔生成点事件表

## 功能
沿路由按固定间隔生成点事件表（路径标识 + 量测值），可直接作为 Locate Features Along Routes 的输入。

量测值从路由几何的 firstPoint.M 步进到 lastPoint.M，步长即间隔；输出为独立表，不是点要素类。


## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：

- 输入路由要素（需先跑 lrs-create-route-by-length 生成）
- 路径标识字段
- 生成间隔（单位与量测值一致，如米；默认 10）
- 输出事件表（GDB 内表名）

## 执行路径
直接执行本技能的 `scripts/run.py`（参数按上表顺序传入）。运行环境：ArcMap

## 执行后复核
- 读回输出的行数/字段值或打开结果文件抽查 3 项；
- 报错时看 traceback 定位到具体参数。

## 参数与调用
```bat
python scripts\run.py <输入路由要素（已带 M 值）> <路径标识字段> <生成间隔（默认 10）> <输出事件表>
```
参数说明：

1. 输入路由要素（已带 M 值）
2. 路径标识字段
3. 生成间隔（默认 10）
4. 输出事件表

## 来源
来自公开开源工具箱的业务口径整理，按业务口径重写为自包含脚本；
原始出处与许可证见 `ATTRIBUTION.md`。
