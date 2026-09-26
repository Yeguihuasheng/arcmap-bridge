# ArcMap Bridge（YghsBridge · ArcMap 版）

> **GitHub 仓库**：<https://github.com/Yeguihuasheng/arcmap-bridge>　·　**演示视频（B 站）**：[ArcgisPro 直连 WorkBuddy 豆包 进行「合法抢劫」](https://www.bilibili.com/video/BV1ESek6zEym)

**用 AI 工具外部驱动 ArcMap** —— 通过 WorkBuddy、豆包、千问、Codex、Claude 等 AI 助手，  
与正在运行的 ArcMap 10.x 建立连接，直接调用 ArcPy / GP 工具完成工作。不用点击、不用复制粘贴、不用手动开 Python 窗口。

> **"外部驱动"就是本项目的主要工作内容**：让 AI 助手成为 ArcMap 的操作者，ArcMap 里发生什么、  
> 做成了什么、导出到哪里，都通过 ArcMap 内的消息面板和通知实时告诉你。

```
AI 工具（WorkBuddy / 豆包 / 千问 / Codex / Claude …）
        │  直连 socket（JSON 协议）
        ▼
arcmap_mcp_client.py ──▶ ArcMap 进程内的 COM 插件 ──▶ arcpy / GP 工具 / ArcObjects
                            │
                            └──▶ ArcMap 内消息面板 + 通知中心（实时"人话"反馈）
```

装上这个插件后，你的 ArcMap 就变成"可被 AI 编程"的：

- 在 ArcMap 的 **Python 2.7 / arcpy** 上下文里跑任意代码
- 跑**任意 GP 工具**（含增删字段、改**被图层引用**的数据结构）
- 读取当前打开的是哪个 .mxd、地图里有哪些图层、数据框、书签
- **在 ArcMap 里看得到**：内置「YGHS Bridge」停靠面板，实时滚动每条任务进度；  
  每次调用结束在通知中心弹一条
- **提示是"人话"**：面板里显示的不是裸的工具名，而是按这次要做什么生成的句子
- 导出物**自动打开所在文件夹**并提示导出位置（PDF / JPG / PNG 截图等）

---

## AI 助手外部驱动（核心用法）

本项目解决的就是一件事：**让 AI 助手"接管" ArcMap**。

你在 AI 工具里说人话，AI 通过本项目的直连客户端驱动 ArcMap 完成实际操作：

| AI 工具                      | 接入方式                                        |
| -------------------------- | ------------------------------------------- |
| **WorkBuddy**              | 让 AI 调用 `arcmap_mcp_client.py`（本仓库自带），对话即驱动 |
| **Claude（Desktop / Code）** | 让 AI 用任意语言封装 `arcmap_mcp_client.py` 的 socket 协议 |
| **豆包 / 千问**                | 同上，封装 `arcmap_mcp_client.py`                     |
| **Codex / 其它编码类 AI**       | 直接 `python arcmap_mcp_client.py <命令>`             |

AI 能做什么（常用命令一览，完整清单见 `arcmap_mcp_client.py`）：

| 命令                          | 作用                              |
| --------------------------- | ------------------------------- |
| `ping`                      | 插件是否在线、ArcMap 版本、当前文档           |
| `info`（get_arcmap_info）     | ArcMap 进程信息、当前 .mxd、图层数           |
| `layers`（list_layers）       | 当前地图与图层清单                       |
| `exec`（execute_code）        | **在 ArcMap 内跑任意 Python（arcpy 可用）** |
| `run_geoprocessing` 等 45+ 项 | 出图、制图、书签、符号化、工作空间、数据源修复等        |

> 说明：本仓库的 `arcmap_mcp_client.py` 是**直连 socket 客户端**，不是 MCP 服务器。  
> 它直接与 ArcMap 进程内的插件对话，AI 只需把「人话需求」翻译成对应的命令调用即可。  
> 若你习惯标准 MCP 接入方式，可用任意 MCP 框架把该客户端包装成 MCP 工具（协议见下文）。

## 功能总览

| 功能                  | 说明                                             |
| ------------------- | ---------------------------------------------- |
| 跑任意 GP 工具           | 含增删字段、改**被图层引用**的数据结构（`run_geoprocessing`）      |
| 在 ArcMap 内跑任意 Python | `execute_code`，py2.7 arcpy 上下文，可读写活 .mxd 快照       |
| 读取文档状态              | 当前 .mxd 路径、全部数据框与各自图层、工作空间、要素类清单              |
| 制图与出图               | 导出 PDF / JPG / PNG、设置比例尺、范围、图层可见性、定义查询        |
| 书签 / 符号化             | 书签增删与跳转、唯一值 / 分级 / 栅格符号化                      |
| 工作空间与数据源            | 读改工作空间、列出要素类/表/栅格、修复断链数据源                    |
| **消息面板**            | 实时滚动任务进度，显示"人话"                                |
| **通知中心**            | 每次调用完成弹一条；失败为高优先级                              |
| 端口固定                | `127.0.0.1:27179`，进程内 STA 线程调度 + 后台 py2.7 子进程，不冻界面 |

## 环境要求

| 你要做什么   | 需要装什么                                  |
| ------- | -------------------------------------- |
| 只用插件    | **ArcMap 10.8+**（Windows，自带 Python 2.7 32 位） |
| 用 AI 驱动 | 再加 **Python 3.6+**（客户端只需标准库，**不用装 arcpy**） |
| 自己编译插件  | 再加 **.NET 8 SDK**（不需要 Visual Studio）   |

### Python 环境说明（重要）

- **插件在 ArcMap 进程内执行 arcpy**：ArcMap 自带 Python 2.7（32 位），脚本按 py2 语义编写，  
  第三方包基本装不了（无 pip 生态），**只用标准库 + arcpy**。
- **客户端是纯 Python 标准库**：`arcmap_mcp_client.py` 只用 `json` + `socket`，  
  **不需要安装 arcpy**，用任意 Python 3 即可跑（驱动环境保持干净）。
- **ArcMap 10.8 自带 Python 路径**：`D:\Work\ArcGIS\Python27\ArcGIS10.8\python.exe`（按你的安装位置）。

## 问询机制（执行约定，强制）

AI 通过本插件执行**任何任务**前，必须遵守以下约定：

1. **先核对参数**：执行前列出任务所需的全部参数（图层/字段/单位/坐标系/输出位置等）
2. **缺一项就停**：任何参数缺失时**暂停执行**，逐项列出缺失项及用途，请用户一次性补全  
   —— 不得自行假设、不得采用未经确认的默认值
3. **确认后严格执行**：按用户确认的参数执行，中途发现新缺失同样停下来问
4. **破坏性操作二次确认**：清空/删除/覆盖类操作，除问询外还须用户再次明确确认
5. **执行后复核**：GetCount / 抽样值 / 成果文件非空，自查后汇报

每个技能的 SKILL.md 自带「使用前必须先问询」清单（见 `skills/`），与本约定配套生效。

## 快速开始

### 1. 构建并安装插件

需要 **ArcMap 10.8+** + **.NET 8 SDK**（不需要 Visual Studio）。仓库自带一键脚本：

```bash
python _build.py            # dotnet build（Release），产出 YghsBridge.AddIn.dll
python YghsBridgeArcMap/package.py   # 打包 add-in（.esriAddIn）
python _install_addin.py    # 安装到 AddIns 目录（需先关闭 ArcMap）
```

### 2. 重启 ArcMap（只需一次）

插件在 ArcMap 启动时加载，之后**永久自动加载**。工具栏出现「YGHS Bridge」面板，  
点击 **MCP 服务（开/关）** 按钮开启 `127.0.0.1:27179` 监听。

### 3. 验证连接

在 AI 工具里（或直接命令行）执行：

```bash
python arcmap_mcp_client.py ping
# -> ok: True, result: {"addin": "yghsBridge 2.13.0 (.NET)", "application": "无标题 - ArcMap", ...}
```

### 4. 跑一段 arcpy（在 ArcMap 内）

```bash
python arcmap_mcp_client.py exec -c "import arcpy; print(arcpy.GetInstallInfo()['Version'])"
# 或执行整个脚本文件
python arcmap_mcp_client.py exec --code-file 脚本.py
```

## 业务技能库（可选，用户自定义）

`skills/` 内置 21 个规划 / 国土业务技能（用地用海指标汇总、三调 DLBM 转换、  
三线占用汇总、批量地类统计、图幅号计算…），对 AI 说  
「执行 skills 里的『用地用海指标汇总』」即可调用。

**这是用户可自定义的部分**：把你自己的工具箱 / GP 工具序列 / arcpy 脚本  
按模板打包成一个 SKILL.md 放进 `skills/`，AI 就能像内置能力一样调用——  
打包与调用方法见 **[skills/README.md](skills/README.md)**。

> 本目录的 skills 从 Pro 版（`arcgis-pro-bridge/skills`）移植而来，执行通道为  
> `execute_code`（py2.7 arcpy），每个技能带独立的 `scripts/run.py` 执行脚本。

## 收尾行为（处理完自动上图 / 打开导出目录）

任务成功后插件会自动收尾，不需要额外写代码：

1. **能上图的产物 → 静默加入当前地图**（要素类 / 独立表 / shapefile；自动去重、输入数据不会被重复加载）
2. **不能上图的导出物 → 打开所在文件夹**（.pdf / .jpg / .png / .csv / .xlsx …），面板提示导出位置
3. 收尾**不会**替你保存 .mxd —— 需要落盘时自行保存

## 安全提示

服务只绑 `127.0.0.1` 且无认证（与 ArcMap 自带 Python 窗口同一信任模型）。  
它能执行任意 Python / GP 工具，**不要**把端口暴露到局域网。

## 目录结构

| 路径                              | 说明                                  |
| ------------------------------- | ----------------------------------- |
| `YghsBridgeArcMap/`             | COM add-in 插件源码（C#，.NET 8）            |
| `arcmap_mcp_client.py`          | 直连客户端（socket 协议，纯标准库）               |
| `_build.py` / `package.py` / `_install_addin.py` | 构建、打包、安装一键脚本               |
| `skills/`                       | 21 个规划/国土业务技能库（见 `skills/README.md`） |
| `bridge_boot.py` / `boot_arcmap.py` | 文件轮询桥兜底通道 + UI 自动化点火              |

## License

MIT —— 见 [LICENSE](LICENSE)。作者：YGHS。

## 相关链接

- **源码 / 问题反馈**：<https://github.com/Yeguihuasheng/arcmap-bridge>
- **演示视频**：<https://www.bilibili.com/video/BV1ESek6zEym>
