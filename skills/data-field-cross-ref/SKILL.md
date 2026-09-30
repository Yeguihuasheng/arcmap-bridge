---
name: data-field-cross-ref
name_zh: 生成字段对照表（源字段到目标字段）
description: 递归扫一个根目录里指定几何类型的要素类，把每个要素类的每个字段登记成一行，再用模糊匹配给它推荐一个目标字段名（可指定一份"目标 schema"要素类作为标准）。输出的对照表 CSV 让人在 Excel 里改完 `to_field_name` 后，交给 `data-merge-by-crossref` 按这张表把异构数据合并成一张。
description_zh: 递归扫一个根目录里指定几何类型的要素类，把每个要素类的每个字段登记成一行，再用模糊匹配给它推荐一个目标字段名（可指定一份"目标 schema"要素类作为标准）。输出的对照表 CSV 让人在 Excel 里改完 `to_field_name` 后，交给 `data-merge-by-crossref` 按这张表把异构数据合并成一张。
argument-hint: <要递归扫描的根目录> <要素类型（Polygon / Polyline / Point / Multipoint / MultiPatch）> <输出对照表 CSV 路径> <目标 schema 要素类或表（可选，填 # 则用全部字段互匹配）> <数据源类型，分号分隔（.shp;.gdb;.mdb；填 # 表示全部）>
user-invocable: true
---

# 生成字段对照表（源字段到目标字段）

## 功能
递归扫一个根目录里指定几何类型的要素类，把每个要素类的每个字段登记成一行，再用模糊匹配给它推荐一个目标字段名（可指定一份"目标 schema"要素类作为标准）。输出的对照表 CSV 让人在 Excel 里改完 `to_field_name` 后，交给 `data-merge-by-crossref` 按这张表把异构数据合并成一张。

## 输出 CSV 列
- `feature_path` 源要素类全路径
- `feature_name` 要素类名
- `from_field_name` 原字段名
- `to_field_name` 建议的目标字段名（**请人工复核后再用于合并**）
- `match_ratio` 模糊匹配相似度（1.00 = 完全一致）
- `field_type` / `field_length` 原字段类型与长度

## 使用前提
- 目标 schema 留空时，`to_field_name` 会退化成"原字段名在全部字段里的模糊最佳匹配"，参考意义有限，**强烈建议指定目标 schema**。
- 模糊匹配用的是 difflib，对中文效果一般，中文字段名基本要靠人工改。
- 生成的 `to_field_name` 只是**建议值**，合并前必须在 Excel 里逐行核对。



## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：

- 要扫描哪个根目录？
- 这批改的是哪种几何类型？（Polygon / Polyline / Point ...）
- 有没有一份"标准字段"的目标要素类/表？有就给路径，没有填 #
- 对照表 CSV 输出到哪里？
- 只想扫哪几种数据源？（全扫就填 #）

## 执行路径
直接执行本技能的 `scripts/run.py`（参数按上表顺序传入）。运行环境：ArcMap

## 执行后复核
- 读回输出的行数/字段值或打开结果文件抽查 3 项；
- 报错时看 traceback 定位到具体参数。

## 参数与调用
```bat
python scripts\run.py <要递归扫描的根目录> <要素类型（Polygon / Polyline / Point / Multipoint / MultiPatch）> <输出对照表 CSV 路径> <目标 schema 要素类或表（可选，填 # 则用全部字段互匹配）> <数据源类型，分号分隔（.shp;.gdb;.mdb；填 # 表示全部）>
```
参数说明：

1. 要递归扫描的根目录
2. 要素类型（Polygon / Polyline / Point / Multipoint / MultiPatch）
3. 输出对照表 CSV 路径
4. 目标 schema 要素类或表（可选，填 # 则用全部字段互匹配）
5. 数据源类型，分号分隔（.shp;.gdb;.mdb；填 # 表示全部）

## 来源
来自公开开源工具箱的业务口径整理，按业务口径重写为自包含脚本；
原始出处与许可证见 `ATTRIBUTION.md`。
