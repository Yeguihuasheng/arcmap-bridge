# 业务技能库（skills）

**这是一个用户可自定义的技能目录**：每个子文件夹 = 一个技能（一份 SKILL.md 说明书 + 一个 `scripts/run.py` 执行脚本），  
AI 通过 yghsBridge ArcMap 桥的 `execute_code` 通道在 ArcMap 内执行。每个技能的 SKILL.md 含  
**问询清单、原帮助文档详细说明、原始实现要点与完整源码（各技能 source/ 目录内）**，部分随附  
resources/ 映射表与模板 Excel。你可以把自己常用的工具箱、GP 工具序列、arcpy 脚本  
打包成一个技能放进来，AI 就能像用内置能力一样调用它。

> 本目录从 Pro 版 `arcgis-pro-bridge/skills` 移植而来，共 **21 个规划/国土业务技能**。  
> 与 Pro 版的差异见文末「与 Pro 版的差异」。

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

## 示例技能清单

以下 21 项为随仓库自带的示例技能（规划/国土业务场景）——演示打包格式，也可直接使用；  
提示词使用示例里的 `xx` 代表图层名、`x:\xx.gdb` 代表数据路径，实际使用时替换为真实值；  
已经加载到地图中的图层，可直接写 xx 代表图层名，不用写全部路径名。

| 技能目录                            | 中文工具名称        | 提示词使用示例                                  | 工具说明                         |
| ------------------------------- | ------------- | ---------------------------------------- | ---------------------------- |
| `plan-check-y-d-change`         | 检查现状规划用地变化    | 「对比 xx现状图层 和 xx规划图层 的用地性质有哪些变化」          | 检测现状与规划用地间的编码/名称差异，输出变化明细    |
| `plan-create-grad-y-d-y-h`      | 生成分级用地用海编码名称  | 「把 x:\xx.gdb\xx 的用地用海编码按大类分级生成编码和名称」     | 由完整编码派生大/中/小类分级编码与名称字段       |
| `plan-create-road-intersection` | 生成道路交叉口       | 「对 x:\xx.gdb 里的道路线生成交叉口」                 | 道路线相交处按转弯半径做交叉口处理            |
| `plan-general-statistic`        | 通用面积统计        | 「统计 x:\xx.gdb\xx 各xx的面积和占比，单位公顷」         | 按任意字段分组统计面积与占比，输出统计表         |
| `plan-line-to-road`             | 线转道路          | 「把 x:\xx.gdb\xx 中心线转为道路，红线宽30米」          | 由中心线按等级宽度生成红线与路缘石线           |
| `plan-multi-statistics`         | 智能汇总统计        | 「以 xx 分区图层为参照，统计 x:\xx.gdb 多个图层落在各分区的面积」 | 多图层按分区范围相交统计，输出智能统计表         |
| `plan-multi-statistics-y-d`     | 批量地类面积统计      | 「按 xx 分区统计 x:\xx.gdb 各地类面积，扣除系数用 xx 字段」  | 多图层分区面积统计，支持扣除系数             |
| `plan-remove0-d-m`              | 移除用地代码后的0     | 「把 x:\xx.gdb\xx 的用地代码后面的0去掉」             | 移除代码尾部补位0（保留2/4位主干）          |
| `plan-s-d-changer`              | 三调DLBM和DLMC转换 | 「把 x:\xx.gdb\xx 的 DLBM 转成 DLMC 名称」       | 三调地类编码与名称互相转换（内置码表）          |
| `plan-s-d2-y-d-y-h`             | 三调转用地用海       | 「把 x:\xx.gdb\xx 的三调名称转成用地用海名称」           | 三调地类名称映射为用地用海名称（新旧版码表）       |
| `plan-s-q-s-x-statistics`       | 三线占用情况汇总表     | 「统计 xx 三线图层落在 xx 分区内的面积，输出汇总表」           | 开发边界/永基农田/生态红线与分区的占用统计       |
| `plan-statistic-load`           | 统计道路网密度       | 「统计 x:\xx.gdb\xx 道路在 xx 范围内的路网密度」        | 按道路类型统计范围内长度与路网密度            |
| `plan-statistics-s-d-l`         | 三调_统计三大类      | 「把 x:\xx.gdb\xx 三调图层按三大类统计面积」            | 三调地类归并农用地/建设用地/未利用地统计        |
| `plan-statistics-x-z-g-h`       | 用地用海现状规划指标汇总  | 「对 xx现状 和 xx规划 图层做用地用海指标对比汇总」            | 现状与规划双列对比的用地用海指标汇总表          |
| `plan-statistics-y-d-y-h`       | 用地用海指标汇总      | 「汇总 x:\xx.gdb\xx 的用地用海指标，单位公顷」           | 按用地用海编码逐级汇总面积与占比             |
| `plan-supply0-d-m`              | 用地代码后补充0      | 「把 x:\xx.gdb\xx 的用地代码补0到6位」              | 代码右补0到指定长度（与移除0互逆）           |
| `plan-updata-y-d-y-h`           | 赋值用地用海编码和名称   | 「给 x:\xx.gdb\xx 图层的要素赋居住用地的编码和名称」        | 批量写入指定用地用海分类的编码与名称           |
| `plan-y-d-y-h-changer`          | 用地用海转换        | 「把 x:\xx.gdb\xx 的用地用海编码转成名称」             | 用地用海编码与名称互相转换（新旧版码表）         |
| `plan-y-d-y-h-old2-new`         | 用地用海旧转新       | 「把 x:\xx.gdb\xx 的旧用地用海编码转成新版编码和名称」       | 旧编码级联转为新版编码与名称               |
| `territory-z-y1`                | 国土空间调查辅助·地类统计 | 「统计 x:\xx.gdb\xx 三调图层各地类的面积」             | 地类统计、三大类归并、编码转换等国土辅助         |
| `gdb-truncate-data`             | 清空GDB要素数据     | 「x:\xx.gdb 清空这个gdb中要素数据」                 | 清理库中要素数据、只保留字段结构，可用作新项目入库初始化 |

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
