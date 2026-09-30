---
name: hydro-dem-from-field
name_zh: 外业测点插值生成 DEM
description: 把外业实测的高程点（深泓点 + 横断面点）合并后插值成 DEM 栅格，支持 Spline（样条）与 TIN 两种方法，并回算每个测点的「实测高程 - DEM 高程」差值做质量检查。用于缺少现成地形数据、只有实测点时的地形重建。
description_zh: 把外业实测的高程点（深泓点 + 横断面点）合并后插值成 DEM 栅格，支持 Spline（样条）与 TIN 两种方法，并回算每个测点的「实测高程 - DEM 高程」差值做质量检查。用于缺少现成地形数据、只有实测点时的地形重建。
argument-hint: <输出要素数据集（须已存在，成果放这里）> <深泓点要素类（带高程字段）> <横断面点要素类（带高程字段）> <高程字段名（默认 Elevation）> <插值方法：Spline（样条）或 TIN> <输出 DEM 像元大小（坐标系单位，如米）> <样条类型：REGULARIZED（规则样条）或 TENSION（张力样条）> <样条权重（REGULARIZED 常用 0.1，TENSION 常用 10）> <参与局部插值的点数（默认 12）>
user-invocable: true
---

# 外业测点插值生成 DEM

## 功能
把外业实测的高程点（深泓点 + 横断面点）合并后插值成 DEM 栅格，支持 Spline（样条）与 TIN 两种方法，并回算每个测点的「实测高程 - DEM 高程」差值做质量检查。用于缺少现成地形数据、只有实测点时的地形重建。

## 输出
- `{要素数据集所在GDB}\DEM_field`：插值出的 DEM 栅格。
- `{要素数据集}\elevation_points`：合并后的高程点，附 `Z`（DEM 采样值）与 `field_dem_diff`（实测−DEM，质检用，绝对值越小越好）。

## 使用前提
- 两类点必须有**同名同型**的高程字段（Merge 要求 schema 一致）。
- Spline 法需 **Spatial Analyst**；TIN 法需 **3D Analyst**；末尾的质检采样（AddSurfaceInformation）始终需要 **3D Analyst**。
- 插值范围 = 测点凸包外扩 1 米（Spline 法）。
- 坐标系沿用输入测点；建议投影坐标系（地理坐标系插值结果不可靠）。



## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：

- 成果放进哪个要素数据集？（须已存在，DEM 存到它所在的 GDB）
- 深泓点、横断面点各是哪个图层？高程字段叫什么？
- 用 Spline 还是 TIN？（Spline 要 Spatial Analyst；TIN 要 3D Analyst）
- 像元大小多少米？样条参数（类型/权重/点数）用默认还是指定？

## 执行路径
直接执行本技能的 `scripts/run.py`（参数按上表顺序传入）。运行环境：ArcMap

## 执行后复核
- 读回输出的行数/字段值或打开结果文件抽查 3 项；
- 报错时看 traceback 定位到具体参数。

## 参数与调用
```bat
python scripts\run.py <输出要素数据集（须已存在，成果放这里）> <深泓点要素类（带高程字段）> <横断面点要素类（带高程字段）> <高程字段名（默认 Elevation）> <插值方法：Spline（样条）或 TIN> <输出 DEM 像元大小（坐标系单位，如米）> <样条类型：REGULARIZED（规则样条）或 TENSION（张力样条）> <样条权重（REGULARIZED 常用 0.1，TENSION 常用 10）> <参与局部插值的点数（默认 12）>
```
参数说明：

1. 输出要素数据集（须已存在，成果放这里）
2. 深泓点要素类（带高程字段）
3. 横断面点要素类（带高程字段）
4. 高程字段名（默认 Elevation）
5. 插值方法：Spline（样条）或 TIN
6. 输出 DEM 像元大小（坐标系单位，如米）
7. 样条类型：REGULARIZED（规则样条）或 TENSION（张力样条）
8. 样条权重（REGULARIZED 常用 0.1，TENSION 常用 10）
9. 参与局部插值的点数（默认 12）

## 来源
来自公开开源工具箱的业务口径整理，按业务口径重写为自包含脚本；
原始出处与许可证见 `ATTRIBUTION.md`。
