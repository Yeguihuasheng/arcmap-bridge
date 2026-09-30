---
name: gpx-to-features
name_zh: 批量 GPX 转要素类
description: 把一个目录下的全部 GPX 文件（手持 GPS / 户外 App 导出的航点、轨迹）批量转换为要素类（waypoint 转点、track/route 转线），并可选地把全部文件合并为一个总要素类。与 `tool-features-to-gpx`（要素导出 GPX）互为逆操作。
description_zh: 把一个目录下的全部 GPX 文件（手持 GPS / 户外 App 导出的航点、轨迹）批量转换为要素类（waypoint 转点、track/route 转线），并可选地把全部文件合并为一个总要素类。与 `tool-features-to-gpx`（要素导出 GPX）互为逆操作。
argument-hint: <含 .gpx 文件的目录> <输出文件地理数据库（不存在则创建）> <是否合并成一个总要素类：true / false>
user-invocable: true
---

# 批量 GPX 转要素类

## 功能
把一个目录下的全部 GPX 文件（手持 GPS / 户外 App 导出的航点、轨迹）批量转换为要素类（waypoint 转点、track/route 转线），并可选地把全部文件合并为一个总要素类。与 `tool-features-to-gpx`（要素导出 GPX）互为逆操作。

## 输出
- `{out_gdb}\{gpx名}`：每个 GPX 一个要素类（点/线取决于 GPX 内容）。
- merge_all=true 时额外输出 `all_runs`（全部文件合并）。

## 使用前提
- GPX 转出坐标系为 WGS84（GPX 标准）；如需投影请再跑 `tool-coordsys-batch`。
- 一个 GPX 若同时含航点与轨迹，GPXtoFeatures 按主类型输出单个要素类。



## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：

- GPX 文件在哪个目录？
- 输出到哪个 GDB？（不存在会自动创建）
- 是否把全部 GPX 合并成一个总要素类？（true=合并，false=各保留一个）

## 执行路径
直接执行本技能的 `scripts/run.py`（参数按上表顺序传入）。运行环境：ArcMap

## 执行后复核
- 读回输出的行数/字段值或打开结果文件抽查 3 项；
- 报错时看 traceback 定位到具体参数。

## 参数与调用
```bat
python scripts\run.py <含 .gpx 文件的目录> <输出文件地理数据库（不存在则创建）> <是否合并成一个总要素类：true / false>
```
参数说明：

1. 含 .gpx 文件的目录
2. 输出文件地理数据库（不存在则创建）
3. 是否合并成一个总要素类：true / false

## 来源
来自公开开源工具箱的业务口径整理，按业务口径重写为自包含脚本；
原始出处与许可证见 `ATTRIBUTION.md`。
