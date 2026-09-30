---
name: hydro-stream-network-points
name_zh: 河网转点并计算流域面积与高程
description: 把编辑好的河网（stream_network）转成线性参考路径，逐折点生成合成测点，给每个点赋上汇流累积值、折算的流域面积（平方英里）与 DEM 高程。用于按汇水面积把河网划分成相对均一的河段。
description_zh: 把编辑好的河网（stream_network）转成线性参考路径，逐折点生成合成测点，给每个点赋上汇流累积值、折算的流域面积（平方英里）与 DEM 高程。用于按汇水面积把河网划分成相对均一的河段。
argument-hint: <输出要素数据集（成果放这里）> <编辑好的河网要素类（带 ReachName 字段）> <汇流累积栅格（hydro-flowdir-d8 的产物）> <输入 DEM 栅格>
user-invocable: true
---

# 河网转点并计算流域面积与高程

## 功能
把编辑好的河网（stream_network）转成线性参考路径，逐折点生成合成测点，给每个点赋上汇流累积值、折算的流域面积（平方英里）与 DEM 高程。用于按汇水面积把河网划分成相对均一的河段。

## 输出
`{要素数据集}\stream_network_points`：每个折点一个点，带 `POINT_X/POINT_Y/POINT_M`（里程，千米）、`Watershed_Area_SqMile`（流域面积，平方英里）、`Z`（DEM 高程）。

## 使用前提
- 需要 **Spatial Analyst**。
- 河网必须带 `ReachName` 字段（每条河段唯一值，路径标识）。
- 汇流累积栅格单位与 DEM 坐标系一致（线性单位须为米，否则面积不换算）。
- 与 `geom-extract-points` 的分工：那个只提几何折点；本技能额外挂汇流面积与高程，是河网分段的业务产物。



## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：

- 成果放进哪个要素数据集？
- 河网要素类是哪个？（ReachName 字段必须已填好）
- 汇流累积栅格与 DEM 各是哪个？

## 执行路径
直接执行本技能的 `scripts/run.py`（参数按上表顺序传入）。运行环境：ArcMap

## 执行后复核
- 读回输出的行数/字段值或打开结果文件抽查 3 项；
- 报错时看 traceback 定位到具体参数。

## 参数与调用
```bat
python scripts\run.py <输出要素数据集（成果放这里）> <编辑好的河网要素类（带 ReachName 字段）> <汇流累积栅格（hydro-flowdir-d8 的产物）> <输入 DEM 栅格>
```
参数说明：

1. 输出要素数据集（成果放这里）
2. 编辑好的河网要素类（带 ReachName 字段）
3. 汇流累积栅格（hydro-flowdir-d8 的产物）
4. 输入 DEM 栅格

## 来源
来自公开开源工具箱的业务口径整理，按业务口径重写为自包含脚本；
原始出处与许可证见 `ATTRIBUTION.md`。
