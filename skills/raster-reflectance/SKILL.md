---
name: raster-reflectance
name_zh: Landsat 波段 DN 值转辐射率与反射率
description: 按 Landsat Level-1 元数据文件（_MTL.txt）把各波段 DN 值先换算成辐射率（Radiance），再按日地距离、太阳高度角与大气外太阳辐照度（ESUN）换算成表观反射率（Reflectance）。支持 Landsat 7 ETM+ / 5 TM / 4 TM 的多套 ESUN 标准。是植被指数、水体指数等定量遥感的前置步骤。
description_zh: 按 Landsat Level-1 元数据文件（_MTL.txt）把各波段 DN 值先换算成辐射率（Radiance），再按日地距离、太阳高度角与大气外太阳辐照度（ESUN）换算成表观反射率（Reflectance）。支持 Landsat 7 ETM+ / 5 TM / 4 TM 的多套 ESUN 标准。是植被指数、水体指数等定量遥感的前置步骤。
argument-hint: <波段影像所在目录（输出也放这里）> <元数据文件路径（_MTL.txt，Level-1 格式）> <ESUN 标准：ETM+ Thuillier / ETM+ ChKur / LPS ACAA Algorithm / Landsat 5 ChKur / Landsat 4 ChKur> <是否保留中间辐射率栅格：true / false> <反射率缩放系数（如 1000 存整型，1 存浮点）> <要处理的波段号，分号分隔（如 1;2;3;4;5;7）>
user-invocable: true
---

# Landsat 波段 DN 值转辐射率与反射率

## 功能
按 Landsat Level-1 元数据文件（_MTL.txt）把各波段 DN 值先换算成辐射率（Radiance），再按日地距离、太阳高度角与大气外太阳辐照度（ESUN）换算成表观反射率（Reflectance）。支持 Landsat 7 ETM+ / 5 TM / 4 TM 的多套 ESUN 标准。是植被指数、水体指数等定量遥感的前置步骤。

## 输出
每个波段在目录下产出 `ReflectanceB{波段}.tif`；keep_rad=true 时另留 `RadianceB{波段}.tif`。

## 使用前提
- 需要 **Spatial Analyst**。
- 元数据必须是 Level-1 `_MTL.txt`（Landsat 7 新格式 RADIANCE_MAXIMUM_BAND_x 与老格式 LMAX_BANDx 都认）。
- 日地距离查随技能打包的 `resources/d.csv`（儒略日 1~366，天文单位）。
- 与 `raster-define-projection` / `raster-define-nodata` 的分工：那两个只改元数据；本技能做辐射定标换算。



## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：

- 波段影像在哪个目录？（_MTL.txt 里登记的波段文件名要能在这个目录找到）
- 元数据 _MTL.txt 的完整路径？
- 用哪套 ESUN 标准？（Landsat 7 常用 ETM+ Thuillier，Landsat 5/4 用各自 ChKur）
- 辐射率中间结果保留吗？反射率缩放系数给多少（1000 便于存整型）？
- 处理哪几个波段？

## 执行路径
直接执行本技能的 `scripts/run.py`（参数按上表顺序传入）。运行环境：ArcMap

## 执行后复核
- 读回输出的行数/字段值或打开结果文件抽查 3 项；
- 报错时看 traceback 定位到具体参数。

## 参数与调用
```bat
python scripts\run.py <波段影像所在目录（输出也放这里）> <元数据文件路径（_MTL.txt，Level-1 格式）> <ESUN 标准：ETM+ Thuillier / ETM+ ChKur / LPS ACAA Algorithm / Landsat 5 ChKur / Landsat 4 ChKur> <是否保留中间辐射率栅格：true / false> <反射率缩放系数（如 1000 存整型，1 存浮点）> <要处理的波段号，分号分隔（如 1;2;3;4;5;7）>
```
参数说明：

1. 波段影像所在目录（输出也放这里）
2. 元数据文件路径（_MTL.txt，Level-1 格式）
3. ESUN 标准：ETM+ Thuillier / ETM+ ChKur / LPS ACAA Algorithm / Landsat 5 ChKur / Landsat 4 ChKur
4. 是否保留中间辐射率栅格：true / false
5. 反射率缩放系数（如 1000 存整型，1 存浮点）
6. 要处理的波段号，分号分隔（如 1;2;3;4;5;7）

## 来源
来自公开开源工具箱的业务口径整理，按业务口径重写为自包含脚本；
原始出处与许可证见 `ATTRIBUTION.md`。
