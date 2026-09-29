---
name: geom-numerate-by-position
name_zh: 按空间位置编号
description: 按要素的空间位置（自上而下 / 自下而上 / 自左而右 等 8 种排序）给点要素类编号并写入新字段，图面编号、出图注记排序常用。
description_zh: 按要素的空间位置（自上而下 / 自下而上 / 自左而右 等 8 种排序）给点要素类编号并写入新字段，图面编号、出图注记排序常用。
argument-hint: <输入点要素类> <排序方式（默认 top_left）> <编号字段名（默认 NUM）>
user-invocable: true
---

# 按空间位置编号

## 功能
按要素的空间位置（自上而下 / 自下而上 / 自左而右 等 8 种排序）给点要素类编号并写入新字段，图面编号、出图注记排序常用。

排序方式：
- `top_left` 自上而下，同高从左到右
- `top_right` 自上而下，同高从右到左
- `bottom_left` 自下而上，同高从左到右
- `bottom_right` 自下而上，同高从右到左
- `right_top` 从右到左，同列自上而下
- `right_bottom` 从右到左，同列自下而上
- `left_top` 从左到右，同列自上而下
- `left_bottom` 从左到右，同列自下而上

编号从 1 开始，写入短整型字段。


## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：

- 输入点要素类（名称或路径）
- 排序方式（top_left / top_right / bottom_left / bottom_right / right_top / right_bottom / left_top / left_bottom，默认 top_left）
- 编号字段名（默认 NUM；已存在同名字段会直接覆写）

## 执行路径
直接执行本技能的 `scripts/run.py`（参数按上表顺序传入）。运行环境：ArcMap

## 执行后复核
- 读回输出的行数/字段值或打开结果文件抽查 3 项；
- 报错时看 traceback 定位到具体参数。

## 参数与调用
```bat
python scripts\run.py <输入点要素类> <排序方式（默认 top_left）> <编号字段名（默认 NUM）>
```
参数说明：

1. 输入点要素类
2. 排序方式（默认 top_left）
3. 编号字段名（默认 NUM）

## 来源
来自公开开源工具箱的业务口径整理，按业务口径重写为自包含脚本；
原始出处与许可证见 `ATTRIBUTION.md`。
