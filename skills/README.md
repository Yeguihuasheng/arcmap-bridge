# 业务技能库（skills）

**这是一个用户可自定义的技能目录**：每个子文件夹 = 一个技能（一份 SKILL.md 说明书 + 一个 `scripts/run.py` 执行脚本），  
AI 通过 yghsBridge ArcMap 桥的 `execute_code` 通道在 ArcMap 内执行。每个技能的 SKILL.md 都含  
**问询清单 + 执行路径 + 执行后复核**，部分随附 `resources/` 映射表与模板。  
本目录里的技能分两类来源，内容组织略有不同：

- **规划/国土业务技能（21 个）**：从 Pro 版移植，SKILL.md 额外带「原帮助文档详细说明 + 原始实现要点」，  
  并附**原窗口源码**（各技能 `source/*.xaml.cs`），便于与 AI 对照校核算法。
- **通用工具技能（112 个）**：按业务口径重写为自包含脚本，附 `ATTRIBUTION.md`（溯源与许可），  
  不带原项目源码。

你可以把自己常用的工具箱、GP 工具序列、arcpy 脚本  
打包成一个技能放进来，AI 就能像用内置能力一样调用它。

> 本目录共 **133 个技能**，已按功能域重新归类（不再按批次），分 13 大类：  
> 国土空间规划与用地用海（34）、字段与属性处理（8）、GDB 与工作空间管理（17）、  
> 几何构造与编辑（25）、线性参考 LRS（5）、栅格与影像（5）、水文分析（14）、地形分析（4）、  
> 制图与文档（3）、数据整理与转换（9）、批量处理（4）、坐标系与投影（2）、空间分析与路径（3）。  
> 详细清单见下文「按功能域分类的技能清单」。与 Pro 版的差异见文末「与 Pro 版的差异」。

## 如何调用技能

对 AI（WorkBuddy / Claude / 豆包等）直接说人话即可，例如：

> 「执行 skills 里的『三调DLBM和DLMC转换』，目标图层是地块，字段 DLBM/DLMC」

AI 的动作链：读取该技能的 SKILL.md → 按里面的问询清单向你确认参数 →  
把参数代入 `scripts/run.py` → 经桥 `execute_code`（py2.7 arcpy）在 **ArcMap 内**执行 →  
读回结果复核，ArcMap 消息面板同步显示执行进度与结果。

## 如何打包自己的工具箱（3 步）

### 第 1 步：建文件夹

在 `skills/` 下新建一个文件夹，**文件夹名 = 技能的唯一英文标识**（建议小写加连字符，  
如 `my-land-balance-table`），不要与现有技能重名。

### 第 2 步：写 SKILL.md（复制下面的模板）

```markdown
---
name: my-land-balance-table
name_zh: 我的用地平衡表
description_zh: 一句话说明功能与用途（AI 靠这句话判断什么时候用这个技能）。
user-invocable: true
---

# 我的用地平衡表

## 功能
一句话说清楚这个技能做什么、适用于什么场景。

## 使用前必须先问询
逐项列出执行前需要用户确认的参数：
- 输入图层（名称或路径）
- 关键字段（地类编码/面积等）
- 算法参数（单位：平方米/公顷/亩、小数位、阈值）
- 输出位置（GDB 要素类 / csv 路径）

## 执行路径（ArcMap 版）
本技能经 yghsBridge ArcMap 桥接执行：把参数代入执行脚本 scripts/run.py，
经桥的 execute_code（py2.7 arcpy）在 ArcMap 内执行。

## 执行后复核
- 读回输出行数 / 抽查字段值 / 确认成果文件非空
```

### 第 3 步：写执行脚本 scripts/run.py 并直接使用

每个技能需要一份 **py2.7 兼容**的执行脚本 `scripts/run.py`，命令行参数驱动，  
`main(...)` 返回 0 表示成功。脚本约定：

```python
# -*- coding: utf-8 -*-
import sys, os, arcpy
sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C   # 公共库：中文安全、读 xlsx、单位换算、三大类归并

def main(fc, field):
    ...
    C.log(u'完成...')   # 中文安全输出（自动编 utf-8）
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
```

无需注册、无需重启 —— 下次对话时 AI 扫描 `skills/` 即可发现并调用。  
执行走桥的 `execute_code` 通道（py2.7 arcpy 子进程），自动上图 / 自动打开导出文件夹等收尾行为照常生效。

## 转换说明：两种方法（按工具箱源码类型选择）

把已有工具箱转成 skills 技能，**按你手里源码的类型**选方法：

### 方法A：纯 Python 工具箱代码 → 直转（最简单）

**适用**：源码本来就是 Python/arcpy 脚本（.py 工具箱脚本、独立 arcpy 脚本、GP 脚本工具）。  
**特点**：代码即最终逻辑，**原样可用**，不需要"翻译"算法——转换置信度最高。  
**示例**：`gdb-truncate-data`（清空GDB要素数据）。

步骤：

1. **存档**：原代码逐字复制到技能目录 `source/original_tool.py`（不改名、不删注释，便于日后校对）
2. **写 SKILL.md**：按上方模板填写，其中：
   - `GetParameterAsText(N)` 的每个参数 → 转成「使用前必须先问询」里的一项
   - `arcpy.AddMessage(...)` → 等效为 `print(...)`（面板可显示）
   - 破坏性操作（删/清空/覆盖）必须在 SKILL.md 里单独加 ⚠️ 确认小节
3. **写 run.py**：把脚本主体封装进 `main(...)`，参数由命令行/`main` 传入
4. **实测**：在沙箱数据（临时 GDB / 测试图层）上跑一遍，核对结果与原工具一致

### 方法B：C# 窗体类工具箱（WPF / Add-in）→ 移植（需提取算法）

**适用**：源码是 C# ArcGIS 加载项（`Show*.cs` 启动器 + 窗口 `.xaml.cs` + `.xaml`）。  
**特点**：算法逻辑要**从 C# 提取改写为 py2.7 arcpy 等效实现**，工作量大但可做到对齐原效果。  
**示例**：仓库里 19 个 plan-*/territory-* 技能均由此法转换。

步骤：

1. **找真逻辑**：`Show<X>.cs` 只是几行启动器，实例化的窗口 `<X>.xaml.cs` 才是算法本体
2. **提取算法**：把 GP 调用序列（全名）、原版 Python codeblock、计算公式、映射表依赖  
   逐条写进 SKILL.md 的「原始实现要点」章节
3. **提取资源**：原码引用的映射表/模板 Excel（如码表、报表模板）复制到技能 `resources/` 子目录
4. **提取参数语义**：原窗体的参数标签、下拉选项、默认值 → 合并进「使用前必须先问询」  
   （AI 按此逐项向用户确认，替代原窗体的交互）
5. **存档源码**：窗口 `.xaml.cs` 复制到 `source/`（供 AI 与校核对照；`.xaml` 界面布局不需要）
6. **写 run.py**：把提取出的算法改写为 py2.7 arcpy 脚本（注意 py2.7 的 unicode/中文路径坑）
7. **实测边界用例**：特别要测**原版算法的特殊分支**（如截断规则、扣减系数），不能只测常规路径

### 两方法对比

|             | 方法A：纯 Python 直转         | 方法B：C# 窗体类移植                    |
| ----------- | ----------------------- | ------------------------------- |
| 适用源码        | .py / arcpy 脚本          | C# 加载项（.xaml.cs）            |
| source/ 存什么 | `original_tool.py`（原代码） | 窗口 `.xaml.cs`（算法）               |
| 算法处理        | 原样可用，仅参数入口改为问询          | 提取改写为 py2.7 arcpy 等效实现                |
| 资源依赖        | 原样带过来                   | 复制到 `resources/` 并在 SKILL.md 标注 |
| 置信度         | 高（逻辑零改写）                | 取决于要点提取完整度（边界用例实测背书）            |
| 工作量         | 小                       | 大（逐窗口读码）                        |

### 通用要求（两种方法都必须）

- **问询优先**：所有参数一律问询确认，不采用未确认的默认值
- **破坏性操作**（清空/删除/覆盖）必须加 ⚠️ 小节 + 执行前二次确认
- **执行后复核**：GetCount / 抽样值 / 文件非空，写进 SKILL.md
- **来源中立**：不带原工具箱的品牌字样；版权/许可不明的第三方代码不要整库搬入

## SKILL.md 字段说明

| 字段                 | 必填 | 说明                                   |
| ------------------ | -- | ------------------------------------ |
| `name`             | 是  | 技能唯一英文标识，与文件夹名一致                     |
| `name_zh`          | 建议 | 中文名，便于用户与 AI 对话时指代                   |
| `description_zh`   | 建议 | 一句话功能描述，**AI 判断何时调用的依据**，写越准越容易被正确唤起 |
| `user-invocable`   | 是  | 固定 `true`                            |

## 写好 SKILL.md 的三个要点

1. **问询清单写全**：AI 执行前会逐项向你确认，列得越全越不会跑偏
2. **执行路径写具体**：GP 工具用全名（`management.Dissolve`）、算法参数带单位和默认值，并指向 `scripts/run.py`
3. **复核项写明确**：让 AI 执行完自查（行数、抽样值、文件非空），出错早暴露

## 按功能域分类的技能清单（133 个）

以下按**功能域**对全部技能重新归类（不再按批次划分），共 13 大类。
每类内技能按使用场景相近的顺序排列。提示词里的 `xx` 代表图层名、`x:\xx.gdb` 代表数据路径，实际使用时替换为真值。

### 一、国土空间规划与用地用海（34 个）

#### 1.1 用地编码与转换（10）

| 技能目录 | 中文名 | 功能说明 |
| --- | --- | --- |
| `plan-s-d-changer` | 三调DLBM和DLMC转换 | 三调地类编码与名称互相转换（内置码表） |
| `plan-s-d2-y-d-y-h` | 三调转用地用海 | 三调地类名称映射为用地用海名称（新旧版码表） |
| `plan-base-convert` | 三调基数转换（DLBM→用地用海） | 按衔接关系一次写入一级代码/名称 + 分类代码/名称，待细分编码单独报出 |
| `plan-y-d-y-h-changer` | 用地用海转换 | 用地用海编码与名称互相转换（新旧版码表） |
| `plan-y-d-y-h-old2-new` | 用地用海旧转新 | 旧编码级联转为新版编码与名称 |
| `plan-create-grad-y-d-y-h` | 生成分级用地用海编码名称 | 由完整编码派生大/中/小类分级编码与名称字段 |
| `plan-remove0-d-m` | 移除用地代码后的0 | 移除代码尾部补位0（保留2/4位主干） |
| `plan-supply0-d-m` | 用地代码后补充0 | 代码右补0到指定长度（与移除0互逆） |
| `plan-updata-y-d-y-h` | 赋值用地用海编码和名称 | 批量写入指定用地用海分类的编码与名称 |
| `plan-code-check` | 地类编码与名称一致性检查 | 逐图斑核对代码/名称匹配，查缺码错码新旧混用，输出问题清单 |

#### 1.2 用地统计与汇总（11）

| 技能目录 | 中文名 | 功能说明 |
| --- | --- | --- |
| `plan-general-statistic` | 通用面积统计 | 按任意字段分组统计面积与占比，输出统计表 |
| `plan-multi-statistics` | 智能汇总统计 | 多图层按分区范围相交统计，输出智能统计表 |
| `plan-multi-statistics-y-d` | 批量地类面积统计 | 多图层分区面积统计，支持扣除系数 |
| `plan-statistics-s-d-l` | 三调统计三大类 | 三调地类归并农用地/建设用地/未利用地统计 |
| `plan-statistics-x-z-g-h` | 用地用海现状规划指标汇总 | 现状与规划双列对比的用地用海指标汇总表 |
| `plan-statistics-y-d-y-h` | 用地用海指标汇总 | 按用地用海编码逐级汇总面积与占比 |
| `plan-s-q-s-x-statistics` | 三线占用情况汇总表 | 开发边界/永基农田/生态红线与分区的占用统计 |
| `plan-yd-statistic` | 用地用海分类统计表 | 按用地用海代码汇总图斑数与面积（㎡/亩/公顷/占比） |
| `plan-yd-overlay` | 用地现状图/规划图叠合生成 | Union 叠合 → 剔碎面 → 查重叠缝隙，输出干净用地图+问题清单 |
| `territory-z-y1` | 国土空间调查辅助·地类统计 | 地类统计、三大类归并、编码转换等国土辅助 |
| `plan-jbnt-occupy` | 永久基本农田占用检查 | 永基农田与占用范围叠加，出被占图斑+占用面积明细 |

#### 1.3 用地检查与拓扑（4）

| 技能目录 | 中文名 | 功能说明 |
| --- | --- | --- |
| `plan-check-y-d-change` | 检查现状规划用地变化 | 检测现状与规划用地间的编码/名称差异，输出变化明细 |
| `plan-topology-check` | 图斑拓扑体检 | 碎面/疑似重叠/几何错误三类问题清单+汇总 |
| `plan-quyu-update` | 街区/街坊/分村区域更新与检查 | 按区域单元统计用地面积回写字段，同时查缝隙/重叠 |
| `plan-fenqu-number` | 用途分区编号生成 | 按空间位置生成连续编号并写入字段，可输出分区面积表 |

#### 1.4 道路与基础设施（4）

| 技能目录 | 中文名 | 功能说明 |
| --- | --- | --- |
| `plan-line-to-road` | 线转道路 | 由中心线按等级宽度生成红线与路缘石线 |
| `plan-create-road-intersection` | 生成道路交叉口 | 道路线相交处按转弯半径做交叉口处理 |
| `plan-road-surface` | 道路面与边线生成 | 由道路中心线按宽度生成道路面，再转道路边线 |
| `plan-statistic-load` | 统计道路网密度 | 按道路类型统计范围内长度与路网密度 |

#### 1.5 成果出图与入库（5）

| 技能目录 | 中文名 | 功能说明 |
| --- | --- | --- |
| `plan-ruku-standardize` | 入库要素规整 | 字段名大写/去空格/统一投影/清 GP 历史/清空图层 一次做完 |
| `plan-cad-import` | 从 CAD 导入（DWG 转 GDB） | DWG→GDB，按 CAD 图层拆点线面注记，汇报各层要素数 |
| `plan-cad-export` | 导出到 CAD（DWG） | 规划图层导出 DWG，方便与设计院对接 |
| `plan-batch-map-export` | 批量出图（布局导出图片） | 工程文件布局批量导出 PNG/PDF/JPEG |
| `plan-setback-buffer` | 控制线与退距管控范围 | 按距离生成退距管控范围，可选融合，并统计范围内被影响图斑 |

### 二、字段与属性处理（8）

| 技能目录 | 中文名 | 功能说明 |
| --- | --- | --- |
| `field-change-type` | 修改字段类型 | 字段改类型（文本转长整/双精度等），不重建表 |
| `field-numeric-type-length` | 数值字段精度与小数位调整 | 调整数值字段类型/长度/精度/小数位 |
| `field-text-length` | 文本字段长度调整 | 按最长串倍数调文本字段长度，避免入库截断 |
| `field-longest-string` | 查找最长字符串值 | 扫描文本字段最长串及长度，作为设字段长度的依据 |
| `field-name-uppercase` | 字段名转大写 | 字段名统一大写，满足部分地方入库命名标准 |
| `field-unique-duplicate-values` | 唯一值与重复值清单 | 列唯一值（可计数），或反向找重复值 |
| `field-update-by-layer` | 按另一图层更新字段 | 用另一图层同名字段回写（等价挂接+字段计算，不落中间结果） |
| `field-delete-by-list` | 按清单批量删除字段 | 按「要素类,字段」清单批量删冗余字段（入库前清理） |

### 三、GDB 与工作空间管理（17）

| 技能目录 | 中文名 | 功能说明 |
| --- | --- | --- |
| `gdb-check-schema` | 两个数据集模式一致性检查 | 逐字段比对名称/类型/别名，输出不一致项 |
| `gdb-export-schema` | 导出数据集结构清单 | 字段名/别名/类型/长度/精度/域等导出存档 |
| `gdb-domain-check` | 属性域合规检查 | 逐字段比对编码值域/数值区间，输出违规清单 |
| `gdb-list-domains` | 列出属性域清单 | 打印全部属性域及编码值/区间，查值域合规 |
| `gdb-list-datasets` | 列出工作空间数据集 | 打印工作空间下要素类/表/要素数据集 |
| `gdb-inventory-csv` | 工作空间数据清单导出 CSV | 清点全部要素类与表成 CSV（路径/数据集/名称/几何） |
| `gdb-list-empty-datasets` | 检出空图层 | 扫描出记录数为 0 的图层，交付前清垃圾 |
| `gdb-count-records-vertices` | 统计记录数与节点数 | 批量统计记录数与折点总数，用于评估数据量/拆分 |
| `gdb-duplicate-field-values` | 字段重复值定位 | 按字段找重复取值及所在行（编码唯一性检查） |
| `gdb-fc-to-gdb-no-history` | 要素类批量导入地理数据库 | 要素类批量入库并关闭地理处理历史，避免膨胀 |
| `gdb-table-to-gdb-no-history` | 表批量导入地理数据库 | 独立表批量入库并关闭地理处理历史 |
| `gdb-find-replace-workspace-paths` | 批量替换工作空间路径 | 数据搬家后批量替换 mxd/图层数据源路径 |
| `gdb-truncate-data` | 清空 GDB 要素数据 | 清理库中要素数据、只保留字段结构，可作新项目入库初始化 |
| `gdb-compact` | 批量压缩地理数据库 | 扫描目录下全部 .gdb 逐个 Compact 回收存储空间 |
| `gdb-to-mdb` | 文件地理数据库批量转个人地理数据库 | 每个源 .gdb 转同名 .mdb（老版本/只用 Access 的协作场景） |
| `gdb-split-by-frame` | 按分区范围拆分地理数据库 | 以分区多边形为界，把源 GDB 全部要素类逐分区裁剪成多个 GDB |
| `tool-dataset-extent-to-features` | 工作空间数据集范围转面 | 含要素类/栅格/要素数据集，带名称/类型/路径/要素数 |

### 四、几何构造与编辑（25）

| 技能目录 | 中文名 | 功能说明 |
| --- | --- | --- |
| `geom-check` | 几何有效性检查 | 跑 CheckGeometry 并汇总问题数量，入库前体检 |
| `geom-explode-repair` | 多部件打散与几何修复 | 多部件→单部件，可选顺带修复几何并删空几何 |
| `geom-boundary-lines` | 提取图斑边界线 | 面→边界线，保留原属性，用于生成地类/行政界线 |
| `geom-polyline-to-polygon` | 闭合线转面 | 闭合多段线→面（如 CAD 导入的界线），保留原坐标系 |
| `geom-fill-holes` | 填补面内空洞 | 按环方向剔除内环，逐要素处理，不需 Advanced 许可 |
| `geom-delete-overlap` | 减去与参照图层的重叠 | 等价 Erase 但不需 Advanced 许可 |
| `geom-cut-by-line` | 用切割线切分要素 | 线自动延长保证横贯，属性复制到每块 |
| `geom-split-line-at-point` | 用点打断线 | 点吸附容差可调，属性复制到每段，多断点递归切分 |
| `line-fixed-length-partition` | 线按固定长度打断 | 等长切分（末段为剩余长度），保留原属性字段 |
| `geom-line-junction-to-point` | 线交点转点（路网节点） | 自身内部也求交，坐标去重，输出带 X/Y/CNT |
| `geom-extract-points` | 线/面提取点 | 7 种取点方式：全部折点/起点/终点/首末/中点/质心/真质心 |
| `geom-group-centroids` | 按字段分组求质心 | 先按字段融合再取每组质心，留空则整层取一个质心 |
| `geom-numerate-by-position` | 按空间位置编号 | 8 种空间排序方式编号，写入短整型字段 |
| `geom-points-to-polygon` | 点按分组顺序连成面 | 点序即边界顺序，输出带分组值与点数 |
| `geom-circle-from-three-points` | 三点定圆 | 每组三点求圆心与半径，输出圆面（可同时输出圆心点） |
| `geom-inner-circle` | 最大内圆 | 迭代收缩逼近求最大内圆与圆心，判断图斑可容纳范围 |
| `geom-convex-hull` | 按分组生成凸包 | 每组点一个最小凸多边形，可外扩缓冲；不分组则整体一个 |
| `geom-thiessen-polygons` | 生成泰森多边形 | 原生 Create Thiessen Polygons，属性保留 |
| `geom-create-fishnet` | 生成渔网格网 | 按原点/旋转/像元/行列生成规则矩形格网（面或线），可选中心标注点 |
| `geom-inside-buffer` | 内侧缓冲带 | 原面−内缩内核=贴边界的内侧环带；太窄的面保留原样 |
| `tool-multi-ring-buffers` | 多环缓冲（含负值内缩） | 逐距离缓冲叠成一个面类，DIST 字段记环距；负值=面向内收缩 |
| `tool-dissolve-fields` | 按字段融合并拼接文本清单 | 融合几何 + 文本清单字段（按源数据出现顺序去重拼接） |
| `geom-rotate-features` | 要素旋转 | 支持绕固定点 / 逐要素质心 / 真实质心旋转，输出新要素类 |
| `geom-spider-graph` | 蜘蛛图（最近设施连线） | 每点连最近参照点，带距离字段；比 OD 矩阵直观 |
| `geom-split-area-by-ratio` | 面积加权分摊属性 | 分摊值=Σ(参照值×重叠面积/参照面积)，面积加权插值 |

### 五、线性参考 LRS（5）

线性参考类技能是**配套链路**：先 `lrs-create-route-by-length` 生成带 M 值的路由，再做事件表 / 站点 / 横断面。

| 技能目录 | 中文名 | 功能说明 |
| --- | --- | --- |
| `lrs-create-route-by-length` | 按长度创建路径（Route） | 线→带量测值 M 的路由，同标识的线合并为一条 |
| `lrs-create-point-event-table` | 按间隔生成点事件表 | 输出「路径标识 + 量测值」表，供 Locate Features Along Routes 用 |
| `lrs-create-line-event-table` | 生成覆盖整条路由的线事件表 | 起止量测值取自路由首尾 M，事件必覆盖整条路由 |
| `lrs-points-along-line` | 沿线等间距生成点 | 先建路由再按间距生成点，同时输出路由要素类，点带 LOC_ANGLE |
| `lrs-station-cross-sections` | 生成桩号点与横断面 | 桩号点 + 按法线方向生成的横断面线（左右各一半宽度） |

### 六、栅格与影像（5）

| 技能目录 | 中文名 | 功能说明 |
| --- | --- | --- |
| `raster-clip-by-mask` | 影像按范围批量裁剪 | 用一个矢量范围批量裁剪一批影像/DEM，按原文件名输出 |
| `raster-define-projection` | 文件夹栅格批量定义坐标系 | 只改元数据不重采样；逐个报告原坐标系被覆盖情况 |
| `raster-define-nodata` | 文件夹栅格批量定义 NoData | 只改元数据不改像元值，登记后自动重建统计 |
| `raster-reflectance` | Landsat 波段 DN 值转辐射率与反射率 | 读 _MTL.txt 元数据，DN→辐射率→表观反射率，5 套 ESUN 标准 |
| `raster-sun-position-hillshade` | 按时刻算太阳位置生成阴影 | 先算太阳方位角/高度角再出山体阴影；夜间输出常量 0 |

### 七、水文分析（14）

多数需要 **Spatial Analyst** 许可（已在说明中标注）。河道地形链路的编排顺序见下。

| 技能目录 | 中文名 | 功能说明 |
| --- | --- | --- |
| `hydro-dem-from-field` | 外业测点插值生成 DEM | Spline/TIN 两法，回算实测−DEM 质检差值（需 3D/Spatial） |
| `hydro-hydrodem` | 把切线烧进 DEM（水文修正） | 沿线取最低高程烧回 DEM，打通堤/坝/路埂挡水处（需 Spatial） |
| `hydro-flowdir-d8` | 填洼+D8 流向+汇流累积 | 一次产出两张流域分析基础栅格（需 Spatial） |
| `hydro-stream-network-points` | 河网转点并计算流域面积与高程 | 折点带里程/汇流面积（平方英里）/DEM 高程（需 Spatial） |
| `hydro-flowline` | 河网按河段整编成河流线 | Dissolve+PAEK 平滑，一条河段一根线 |
| `hydro-flowline-points` | 河流线生成纵剖面测点 | LRS 路径+站距加密，带里程/Z，可选校准点校正里程（需 3D） |
| `hydro-xs-points` | 横断面线生成测点 | 按间距等分测点，带 SEQ/里程/坐标/高程（可选 DEM 采样） |
| `hydro-xs-classify-points` | 横断面测点按河道/滩地分类 | 原地加 channel/floodplain 标记字段，糙率分区用 |
| `hydro-centerline` | 由河道面提取中心线 | 栅格化→Thin 骨架→栅格转线→PAEK 平滑；像元建议 ≤ 河宽/100 |
| `hydro-channel-slope` | 河道范围内坡度栅格 | Slope+按面裁剪；平均比降可配分区统计 |
| `hydro-detrend-dem` | DEM 河谷趋势面剥离 | 河流线采样→IDW 趋势面→平滑→相减，谷底去趋势值≈0 |
| `hydro-water-surface-extent` | 按去趋势高度圈水面范围 | 阈值掩膜→栅格转面→可选平滑（与去趋势配套） |
| `hydro-trace-downstream` | 按流向栅格追踪下游路径 | 逐像元追到洼地或边界，输出带起点编号/步数/长度/终止类型的线 |
| `hydro-watershed-by-point` | 逐点划分流域 | Snap Pour Point+Watershed，可选地类面积统计 |

### 八、地形分析（4）

| 技能目录 | 中文名 | 功能说明 |
| --- | --- | --- |
| `terrain-identify-depressions` | 识别地形洼地 | Fill→相减→重分类→转面→按面积过滤（需 Spatial） |
| `terrain-identify-geodepressions` | 识别负地形洼地（带深度） | 填洼差值找坑，面积窗口过滤，每坑带最大深度 POCK_DEP（需 Spatial） |
| `terrain-delineate-flowpaths` | 按出口面划分汇水区 | D8 流向+面倾泻点，一次出多个汇水区多边形（需 Spatial） |
| `terrain-profile` | 沿线路生成地形剖面 | Stack Profile 剖面表（距离/高程），可选导出剖面图（需 3D Analyst） |

### 九、制图与文档（3）

| 技能目录 | 中文名 | 功能说明 |
| --- | --- | --- |
| `map-create-graticule` | 生成经纬网（标准分幅格网） | 经线+纬线带 DMS 标注与十进制度字段，输出固定 WGS84 |
| `meta-export-xml` | 批量导出元数据 XML（精确副本） | 走 Desktop 自带 exact copy of.xslt，不改写同步信息 |
| `mxd-list-data-sources` | 列出 MXD 数据源清单 | 逐图层列数据源路径（可扫文件夹），交付前断链检查 |

### 十、数据整理与转换（9）

| 技能目录 | 中文名 | 功能说明 |
| --- | --- | --- |
| `data-metadata-dump` | 跨目录递归盘点要素类与结构 | 递归扫目录树，输出要素级表 + 字段级表（用 FEAT_UUID 关联） |
| `data-field-cross-ref` | 生成字段对照表 | 模糊匹配推荐目标字段名，人在 Excel 核完再交给下一个技能 |
| `data-merge-by-crossref` | 按字段对照表合并异构要素类 | 逐源投影→搬字段→合并，保留 MERGED_SRC 记录来源 |
| `data-unzip-dir` | 批量解压 ZIP | 递归扫描子目录，每包解压到同名子文件夹 |
| `table-export-csv-excel` | 属性表导出 CSV / Excel | 要素类/表属性导出 CSV 或 Excel，供统计上报 |
| `tool-features-to-gpx` | 要素导出 GPX | 点→wpt、线→trk（GPX 1.1），自动投影 WGS84，带名称/描述/高程 |
| `gpx-to-features` | 批量 GPX 转要素类 | 目录下 GPX 批量转要素类（waypoint→点、track/route→线），可选合并 |
| `tool-blob-to-file` | BLOB 字段批量导出文件 | 逐记录落盘，文件名取自字段值，同名自动加后缀 |
| `tool-file-to-blob` | 文件批量写入 BLOB 字段 | 与上面互为逆操作；文件名匹配字段值，找不到的逐条列出 |

### 十一、批量处理（4）

| 技能目录 | 中文名 | 功能说明 |
| --- | --- | --- |
| `tool-batch-clip` | 批量裁剪 | 用一个裁剪范围批量裁一批图层 |
| `tool-batch-merge` | 批量合并图层 | 结构相同的一批图层合并成一张总图 |
| `tool-batch-rename` | 批量重命名数据集 | 批量改名：加前缀 / 加后缀 / 查找替换 |
| `tool-batch-split-by-field` | 按字段值拆分图层 | 按某字段取值把一个图层拆成多份 |

### 十二、坐标系与投影（2）

| 技能目录 | 中文名 | 功能说明 |
| --- | --- | --- |
| `tool-coordsys-batch` | 批量定义 / 投影坐标系 | 对一批图层批量定义或投影坐标系 |
| `coord-four-parameter` | 四参数坐标转换 | 用同名控制点最小二乘求平面四参数（平移/缩放/旋转），可选转换要素类 |

### 十三、空间分析与路径（3）

| 技能目录 | 中文名 | 功能说明 |
| --- | --- | --- |
| `analysis-near-by-group` | 按分组求组内最近要素距离 | 逐组选集 + Near，结果写回输入（需 ArcInfo 许可） |
| `path-smooth-shortest` | 按坡度限制找最短路径 | Dijkstra + 三维距离代价，超坡不可通行；需投影坐标系 DEM |
| `suitability-weighted-overlay` | 加权叠加适宜性评价 | 多因子重分类→加权求和→按排除规则扣禁建区→按分值圈候选地块（需 Spatial） |

### 河道地形数据链（水文+地形跨类编排参考）

把「外业测点 → 可用 DEM → 河网 → 河流线 → 纵/横断面」串成一条完整链路（按使用顺序）：

1. `hydro-dem-from-field` 外业点插值建 DEM（或直接用现成 DEM）
2. `hydro-hydrodem` 烧切线修正 DEM（可选，打通挡水处）
3. `hydro-flowdir-d8` 填洼 + D8 流向 + 汇流累积
4. `hydro-stream-network-points` 河网转点、按汇流面积分段
5. `hydro-flowline` 河网整编成河流线
6. `hydro-flowline-points` 布纵剖面测点
7. `hydro-xs-points` 布横断面测点 → `hydro-xs-classify-points` 分类
8. 需要水面范围时：`hydro-detrend-dem` 去趋势 → `hydro-water-surface-extent` 圈水面

## 与 Pro 版的差异

本目录从 Pro 版 `arcgis-pro-bridge/skills` 移植，通道与实现有差异：

| | Pro 版 | ArcMap 版（本目录） |
|---|---|---|
| 执行通道 | `run_python`/`run_gp`（QueuedTask 进程内） | 桥的 `execute_code`（py2.7 arcpy 子进程） |
| 执行脚本 | SKILL.md 内嵌 arcpy 说明 | 独立 `scripts/run.py`（命令行参数） |
| 读取 xlsx | openpyxl | **xlrd**（py2.7 已装） |
| 输出表格 | 模板 .xlsx（Aspose.Cells） | **CSV（utf-8-sig，Excel 可开）** |
| 精确几何 | Pro SDK GeometryEngine | `plan-line-to-road`、`plan-create-road-intersection` 为 **Buffer/Intersect 近似降级** |

### py2.7 移植要点（写 run.py 必看）

1. **中文路径/字段**：脚本统一 `import _common as C`，用 `C.S()` 包 cursor 读出的字段值，  
   命令行传入的中文路径由 `_common._patch_argv()` 转 unicode。
2. **资源定位**：桥的 `exec()` 里 `__file__` 未定义，定位 resources 用 `C.skill_dir(name)` / `C.resource_path(name, ...)`，  
   别用 `os.path.abspath(__file__)`。
3. **地理坐标系面积/长度**：`!shape.area!`/`!shape.length!` 在无投影坐标系返回平方度/度，  
   一律用 `C.area_expr(type, dataset)` / `C.length_expr(dataset)`（内部 `is_geographic()` 自动切测地面积/长度）。
4. **输出 .shp 路径歧义**：输出到普通文件夹生成 `.shp`，中间层用 `in_memory`，最后 `CopyFeatures` 落盘并补 `.shp` 扩展名。
