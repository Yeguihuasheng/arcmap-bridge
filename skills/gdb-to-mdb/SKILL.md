---
name: gdb-to-mdb
name_zh: 文件地理数据库批量转个人地理数据库
description: 把指定目录下的全部文件地理数据库（*.gdb）批量转换为个人地理数据库（*.mdb，Access 格式），每个源 GDB 对应一个同名 MDB。适用于需要与老版本 ArcMap（9.x/10.x 早期）或只用 Access 的协作方交换数据的场景。
description_zh: 把指定目录下的全部文件地理数据库（*.gdb）批量转换为个人地理数据库（*.mdb，Access 格式），每个源 GDB 对应一个同名 MDB。适用于需要与老版本 ArcMap（9.x/10.x 早期）或只用 Access 的协作方交换数据的场景。
argument-hint: <源目录（其下 *.gdb 全部转换）> <输出目录（存放生成的 *.mdb）>
user-invocable: true
---

# 文件地理数据库批量转个人地理数据库

## 功能
把指定目录下的全部文件地理数据库（*.gdb）批量转换为个人地理数据库（*.mdb，Access 格式），每个源 GDB 对应一个同名 MDB。适用于需要与老版本 ArcMap（9.x/10.x 早期）或只用 Access 的协作方交换数据的场景。

## 输出
- `{输出目录}\{源名}.mdb`：每个源 GDB 对应一个同名个人地理数据库，内含源库全部要素类。

## 使用前提
- Personal GDB 为 Access 32 位格式，单库上限约 2GB。
- 独立表（ListTables）本技能不转，仅转要素类（ListFeatureClasses）。
- 名称含中文时按系统编码处理；目标 MDB 已存在会先删除再重建。



## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：

- 源 GDB 目录？（目录下所有 .gdb 都会被转换）
- MDB 输出到哪个目录？
- 注意：Personal GDB（.mdb）是 32 位 Access 格式，容量上限约 2GB，超大数据集会失败；确认是否仍需要 .mdb 交付？

## 执行路径
直接执行本技能的 `scripts/run.py`（参数按上表顺序传入）。运行环境：ArcMap

## 执行后复核
- 读回输出的行数/字段值或打开结果文件抽查 3 项；
- 报错时看 traceback 定位到具体参数。

## 参数与调用
```bat
python scripts\run.py <源目录（其下 *.gdb 全部转换）> <输出目录（存放生成的 *.mdb）>
```
参数说明：

1. 源目录（其下 *.gdb 全部转换）
2. 输出目录（存放生成的 *.mdb）

## 来源
来自公开开源工具箱的业务口径整理，按业务口径重写为自包含脚本；
原始出处与许可证见 `ATTRIBUTION.md`。
