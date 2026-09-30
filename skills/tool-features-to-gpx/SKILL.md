---
name: tool-features-to-gpx
name_zh: 要素导出 GPX
description: 把点或线要素导出为 GPX 1.1 文件：点转 waypoint（wpt）、线转 track（trk），可指定名称与描述字段。导出后可直接拷给手持 GPS、两步路、户外助手、Google Earth 使用。
description_zh: 把点或线要素导出为 GPX 1.1 文件：点转 waypoint（wpt）、线转 track（trk），可指定名称与描述字段。导出后可直接拷给手持 GPS、两步路、户外助手、Google Earth 使用。
argument-hint: <输入点或线要素> <名称字段（GPX 里的 name；填 # 用要素 OID）> <描述字段（GPX 里的 desc；填 # 留空）> <输出 GPX 文件路径（.gpx）>
user-invocable: true
---

# 要素导出 GPX

## 功能
把点或线要素导出为 GPX 1.1 文件：点转 waypoint（wpt）、线转 track（trk），可指定名称与描述字段。导出后可直接拷给手持 GPS、两步路、户外助手、Google Earth 使用。

## 使用前提
- 输入应为 **WGS84 经纬度坐标系**（GPX 标准要求）；其它坐标系会自动投影到 EPSG:4326（跨基准用 ArcGIS 默认变换）。
- 点 → wpt；线 → trk/trkseg（每条线一个 track）；**面要素不支持**。
- Z 值会写进 GPX 的 ele（高程，米）。
- GPX 只保留名称/描述/高程，其它属性不导出（GPX 标准限制）。



## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：

- 输入点/线要素是哪个？
- 哪个字段做名称？（填 # 就用要素编号）
- 哪个字段做描述？（不需要填 #）
- GPX 文件输出到哪里？

## 执行路径
直接执行本技能的 `scripts/run.py`（参数按上表顺序传入）。运行环境：ArcMap

## 执行后复核
- 读回输出的行数/字段值或打开结果文件抽查 3 项；
- 报错时看 traceback 定位到具体参数。

## 参数与调用
```bat
python scripts\run.py <输入点或线要素> <名称字段（GPX 里的 name；填 # 用要素 OID）> <描述字段（GPX 里的 desc；填 # 留空）> <输出 GPX 文件路径（.gpx）>
```
参数说明：

1. 输入点或线要素
2. 名称字段（GPX 里的 name；填 # 用要素 OID）
3. 描述字段（GPX 里的 desc；填 # 留空）
4. 输出 GPX 文件路径（.gpx）

## 来源
来自公开开源工具箱的业务口径整理，按业务口径重写为自包含脚本；
原始出处与许可证见 `ATTRIBUTION.md`。
