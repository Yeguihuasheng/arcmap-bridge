---
name: hydro-flowdir-d8
name_zh: 填洼并生成 D8 流向与汇流累积
description: 对 DEM 依次做填洼（Fill）→ D8 流向（Flow Direction）→汇流累积（Flow Accumulation），一次产出后续流域分析需要的两张基础栅格。是 `hydro-watershed-by-point` 的前置步骤。
description_zh: 对 DEM 依次做填洼（Fill）→ D8 流向（Flow Direction）→汇流累积（Flow Accumulation），一次产出后续流域分析需要的两张基础栅格。是 `hydro-watershed-by-point` 的前置步骤。
argument-hint: <输入 DEM 栅格> <输出位置（文件夹或地理数据库）>
user-invocable: true
---

# 填洼并生成 D8 流向与汇流累积

## 功能
对 DEM 依次做填洼（Fill）→ D8 流向（Flow Direction）→汇流累积（Flow Accumulation），一次产出后续流域分析需要的两张基础栅格。是 `hydro-watershed-by-point` 的前置步骤。

## 使用前提
- 需要 **Spatial Analyst** 扩展许可。
- 固定输出名：`flow_direction_d8`（整型 D8 编码 1/2/4/…/128）与 `flow_accumulation_d8`（FLOAT，汇入每个像元的像元数）。输出到文件夹时自动加 `.tif`（GRID 格式名长受限）。
- DEM 建议预先做水文修正（挖掉桥梁/涵洞处的假洼地）；本工具的 Fill 只做常规填洼。
- 中间结果（填洼面）只存在内存，超大 DEM 可能吃内存，建议分流域跑。
- ArcMap 版没有并行参数（Pro 的 parallelProcessingFactor），大 DEM 耗时会更长。



## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：

- DEM 是哪个？
- 两张结果栅格（flow_direction_d8 / flow_accumulation_d8）输出到哪个文件夹或 GDB？

## 执行路径
直接执行本技能的 `scripts/run.py`（参数按上表顺序传入）。运行环境：ArcMap

## 执行后复核
- 读回输出的行数/字段值或打开结果文件抽查 3 项；
- 报错时看 traceback 定位到具体参数。

## 参数与调用
```bat
python scripts\run.py <输入 DEM 栅格> <输出位置（文件夹或地理数据库）>
```
参数说明：

1. 输入 DEM 栅格
2. 输出位置（文件夹或地理数据库）

## 来源
来自公开开源工具箱的业务口径整理，按业务口径重写为自包含脚本；
原始出处与许可证见 `ATTRIBUTION.md`。
