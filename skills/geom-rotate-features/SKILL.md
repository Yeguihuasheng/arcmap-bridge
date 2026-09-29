---
name: geom-rotate-features
name_zh: 要素旋转
description: 按给定角度旋转整个要素类，支持绕指定坐标点旋转、或绕每个要素自身的质心/真实质心旋转，输出到新的要素类（不改动原始数据）。
description_zh: 按给定角度旋转整个要素类，支持绕指定坐标点旋转、或绕每个要素自身的质心/真实质心旋转，输出到新的要素类（不改动原始数据）。
argument-hint: <输入要素类> <输出要素类> <旋转基准（xy / in_feature_centroid / in_feature_true_centroid）> <旋转角度（度，逆时针为正）> <旋转中心 X（xy 模式必填，其它填 0）> <旋转中心 Y（xy 模式必填，其它填 0）>
user-invocable: true
---

# 要素旋转

## 功能
按给定角度旋转整个要素类，支持绕指定坐标点旋转、或绕每个要素自身的质心/真实质心旋转，输出到新的要素类（不改动原始数据）。

角度单位：度，逆时针为正。

`xy` 模式绕固定点（填旋转中心 X/Y）；`in_feature_centroid` / `in_feature_true_centroid` 为逐要素绕自身质心旋转（常用于图斑微调、符号摆正）。


## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：

- 输入要素类（名称或路径）
- 输出要素类
- 旋转基准（xy 固定点 / in_feature_centroid 质心 / in_feature_true_centroid 真实质心）
- 旋转角度（度，逆时针为正）
- xy 模式下的旋转中心 X / Y（其它模式填 0）
- 坐标系要求：必须为投影坐标系

## 执行路径
直接执行本技能的 `scripts/run.py`（参数按上表顺序传入）。运行环境：ArcMap

## 执行后复核
- 读回输出的行数/字段值或打开结果文件抽查 3 项；
- 报错时看 traceback 定位到具体参数。

## 参数与调用
```bat
python scripts\run.py <输入要素类> <输出要素类> <旋转基准（xy / in_feature_centroid / in_feature_true_centroid）> <旋转角度（度，逆时针为正）> <旋转中心 X（xy 模式必填，其它填 0）> <旋转中心 Y（xy 模式必填，其它填 0）>
```
参数说明：

1. 输入要素类
2. 输出要素类
3. 旋转基准（xy / in_feature_centroid / in_feature_true_centroid）
4. 旋转角度（度，逆时针为正）
5. 旋转中心 X（xy 模式必填，其它填 0）
6. 旋转中心 Y（xy 模式必填，其它填 0）

## 来源
来自公开开源工具箱的业务口径整理，按业务口径重写为自包含脚本；
原始出处与许可证见 `ATTRIBUTION.md`。
