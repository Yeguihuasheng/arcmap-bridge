---
name: meta-export-xml
name_zh: 批量导出元数据 XML（精确副本）
description: 把一批数据集的元数据按「精确副本」样式（exact copy of.xslt）逐个导出成 XML 文件，不改写同步信息。用于成果归档、元数据批量送审、把元数据转移到别的平台。
description_zh: 把一批数据集的元数据按「精确副本」样式（exact copy of.xslt）逐个导出成 XML 文件，不改写同步信息。用于成果归档、元数据批量送审、把元数据转移到别的平台。
argument-hint: <数据集列表（分号分隔，要素类/表/栅格/图层均可）> <XML 输出目录>
user-invocable: true
---

# 批量导出元数据 XML（精确副本）

## 功能
把一批数据集的元数据按「精确副本」样式（exact copy of.xslt）逐个导出成 XML 文件，不改写同步信息。用于成果归档、元数据批量送审、把元数据转移到别的平台。

## 使用前提
- 走 ArcGIS Desktop 自带的 `Metadata/Stylesheets/gpTools/exact copy of.xslt` 样式表；若安装组件缺失会明确报错。
- 输出文件名 = 数据集名.xml，同名自动加 `_1/_2`。
- 元数据为空的数据集也会生成 XML（骨架），属正常。
- 想改完再导回：在 ArcCatalog 里用「导入元数据」选这些 XML。



## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：

- 要导出哪些数据集？（分号分隔列出全部）
- XML 输出到哪个目录？

## 执行路径
直接执行本技能的 `scripts/run.py`（参数按上表顺序传入）。运行环境：ArcMap

## 执行后复核
- 读回输出的行数/字段值或打开结果文件抽查 3 项；
- 报错时看 traceback 定位到具体参数。

## 参数与调用
```bat
python scripts\run.py <数据集列表（分号分隔，要素类/表/栅格/图层均可）> <XML 输出目录>
```
参数说明：

1. 数据集列表（分号分隔，要素类/表/栅格/图层均可）
2. XML 输出目录

## 来源
来自公开开源工具箱的业务口径整理，按业务口径重写为自包含脚本；
原始出处与许可证见 `ATTRIBUTION.md`。
