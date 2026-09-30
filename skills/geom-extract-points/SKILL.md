---
name: geom-extract-points
name_zh: 从线/面要素提取点（顶点/端点/中点/质心）
description: 把线或面要素转换成点要素，可选 7 种取点方式：全部折点、起点、终点、首末两点、中点、质心（重心）、真质心（面积质心）。属性全部保留。用于批量生成标注点、界桩点、断面桩点、把面转点做后续分析。
description_zh: 把线或面要素转换成点要素，可选 7 种取点方式：全部折点、起点、终点、首末两点、中点、质心（重心）、真质心（面积质心）。属性全部保留。用于批量生成标注点、界桩点、断面桩点、把面转点做后续分析。
argument-hint: <输入线或面要素> <输出点要素> <取点方式：ALL/START/END/MID/BOTH_ENDS/CENTROID/TRUE_CENTROID>
user-invocable: true
---

# 从线/面要素提取点（顶点/端点/中点/质心）

## 功能
把线或面要素转换成点要素，可选 7 种取点方式：全部折点、起点、终点、首末两点、中点、质心（重心）、真质心（面积质心）。属性全部保留。用于批量生成标注点、界桩点、断面桩点、把面转点做后续分析。

## 取点方式对照
| 方式 | 含义 | 典型用途 |
|---|---|---|
| ALL | 每个折点一个点 | 提取界桩/节点 |
| START / END | 起点 / 终点 | 河源、河口 |
| BOTH_ENDS | 首末各一个点 | 管段两端 |
| MID | 线长一半处 | 道路中桩 |
| CENTROID | 几何重心（顶点平均） | 快速标注 |
| TRUE_CENTROID | 面积质心（必在面内附近） | 面标注推荐 |

## 使用前提
- ALL/START/END/MID/BOTH_ENDS 走原生 Feature Vertices To Points；CENTROID/TRUE_CENTROID 逐要素读几何计算，凹多边形的 CENTROID 可能落在面外，要落面内用 TRUE_CENTROID。
- 属性全部保留；输出建议 GDB（shp 字段名截 10 字符）。
- 多部件要素：ALL/BOTH_ENDS 逐部件取点；CENTROID 取整体一个。



## 使用前必须先问询（缺一不可）
用 AskUserQuestion 逐项确认下列参数，全部明确后才执行；不确定的给候选值让用户选：

- 输入线/面要素是哪个？
- 输出点要素到哪里？
- 要哪种点？全部折点(ALL)/起点(START)/终点(END)/首末两点(BOTH_ENDS)/中点(MID)/质心(CENTROID)/真质心(TRUE_CENTROID)

## 执行路径
直接执行本技能的 `scripts/run.py`（参数按上表顺序传入）。运行环境：ArcMap

## 执行后复核
- 读回输出的行数/字段值或打开结果文件抽查 3 项；
- 报错时看 traceback 定位到具体参数。

## 参数与调用
```bat
python scripts\run.py <输入线或面要素> <输出点要素> <取点方式：ALL/START/END/MID/BOTH_ENDS/CENTROID/TRUE_CENTROID>
```
参数说明：

1. 输入线或面要素
2. 输出点要素
3. 取点方式：ALL/START/END/MID/BOTH_ENDS/CENTROID/TRUE_CENTROID

## 来源
来自公开开源工具箱的业务口径整理，按业务口径重写为自包含脚本；
原始出处与许可证见 `ATTRIBUTION.md`。
