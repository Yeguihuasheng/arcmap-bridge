using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
using AddInButton = ESRI.ArcGIS.Desktop.AddIns.Button;
using AddInComboBox = ESRI.ArcGIS.Desktop.AddIns.ComboBox;

namespace YghsBridge.AddIn
{
    /// <summary>
    /// 问题反馈要跳转的外链 —— 只改这里，不用动其它代码（对齐 Pro 版 Links）。
    /// </summary>
    internal static class Links
    {
        // 本插件的开源仓库（问题反馈 → Issues）。ArcMap 版独立仓库。
        public const string Github = "https://github.com/Yeguihuasheng/arcmap-bridge";

        // 演示/教学视频（B 站）：ArcGIS Pro 直连 WorkBuddy（豆包）进行「合法抢劫」。
        public const string Bilibili = "https://www.bilibili.com/video/BV1ESek6zEym?vd_source=9495744f46cb9ac34a88358f9672b605";
    }

    /// <summary>用系统默认浏览器打开链接，并在面板里记一行（对齐 Pro 版 UrlLauncher）。</summary>
    internal static class UrlLauncher
    {
        public static void Open(string url, string label)
        {
            try
            {
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
                BridgeLog.Note("打开链接：" + label + " → " + url);
            }
            catch (Exception ex)
            {
                BridgeLog.Note("打开链接失败（" + label + "）：" + ex.Message);
            }
        }
    }

    /// <summary>
    /// 工具栏「yghsBridge」的按钮。
    /// MCP 服务做成**单一动态开关按钮**（对齐 Pro 版 McpToggle）：ArcMap 的 add-in Button
    /// 无法热切换彩色/灰色图标，故用 caption 文字 + Checked 按下态表达开/关。
    /// </summary>
    public class ToggleMcpButton : AddInButton
    {
        protected override void OnClick()
        {
            McpExtension ext = McpExtension.Instance;
            if (ext == null)
            {
                MessageBox.Show("MCP 扩展未加载。", "yghsBridge · 错误");
                return;
            }

            if (ext.IsRunning)
            {
                ext.StopServer();
                BridgeLog.Note("桥接服务已停止");
                MessageBox.Show("桥接服务已成功停止。外部 AI 暂时无法连接。",
                                "yghsBridge · 桥接已停止");
            }
            else
            {
                string error = ext.StartServer();
                if (error == null)
                {
                    BridgeLog.Note("桥接服务已启动，监听 127.0.0.1:" + McpServer.Port);
                    MessageBox.Show(
                        "桥接服务已启动，正在监听 127.0.0.1:" + McpServer.Port + "。\n"
                        + "请保持 ArcMap 打开以维持连接。\n\n"
                        + "可用「消息面板」按钮查看实时日志。",
                        "yghsBridge · 桥接已启动");
                }
                else
                {
                    MessageBox.Show("无法启动桥接服务：\n" + error,
                                    "yghsBridge · 错误");
                }
            }
        }

        protected override void OnUpdate()
        {
            McpExtension ext = McpExtension.Instance;
            bool run = ext != null && ext.IsRunning;
            Enabled = true;
            Checked = run;                       // 按下态 = 服务运行中
            Caption = run ? "MCP 服务（开）" : "MCP 服务（关）";
            Message = run
                ? "MCP 服务运行中（点击停止）。"
                : "MCP 服务已停止（点击启动）。";
            Tooltip = run
                ? "yghsBridge 桥接服务运行中，监听 127.0.0.1:" + McpServer.Port
                : "yghsBridge 桥接服务已停止";
        }
    }

    /// <summary>问题反馈 → GitHub 仓库（直接打开，对齐 Pro 版 LinkGithubButton）。</summary>
    public class FeedbackButton : AddInButton
    {
        protected override void OnClick()
        {
            UrlLauncher.Open(Links.Github, "GitHub 仓库");
        }

        protected override void OnUpdate()
        {
            Enabled = true;
        }
    }

    /// <summary>演示/教学视频 → B 站（直接打开，对齐 Pro 版外链按钮）。</summary>
    public class BilibiliButton : AddInButton
    {
        protected override void OnClick()
        {
            UrlLauncher.Open(Links.Bilibili, "B 站视频");
        }

        protected override void OnUpdate()
        {
            Enabled = true;
        }
    }

    /// <summary>
    /// 诊断信息：当外部助手「连不上」时，最需要知道的信息。可直接打开日志文件
    /// （几乎总是排查的下一步）。
    /// </summary>
    public class StatusMcpButton : AddInButton
    {
        protected override void OnClick()
        {
            McpExtension ext = McpExtension.Instance;
            bool run = ext != null && ext.IsRunning;
            Version v = typeof(StatusMcpButton).Assembly.GetName().Version;

            string texto =
                "桥接\n"
                + "  状态:        " + (run ? "运行中，正在监听" : "已停止") + "\n"
                + "  地址:        127.0.0.1:" + McpServer.Port + "\n"
                + "  插件:        yghsBridge " + v.ToString(3) + " (.NET)\n"
                + "  更新检查:     " + Diagnostico.DescribirActualizacion() + "\n"
                + "  自动启动:     " + (Ajustes.Autoarranque ? "是（打开 ArcMap 时自动启动）" : "否（需手动点击启动）") + "\n"
                + "\n会话\n"
                + "  文档:         " + DescribirDocumento() + "\n"
                + "  自:           " + Estadisticas.Inicio.ToString("HH:mm:ss") + "\n"
                + "  请求数:       " + Estadisticas.Peticiones + "\n"
                + "  最近:         " + Estadisticas.UltimoComando + "\n"
                + "  错误数:       " + Estadisticas.Errores + "\n"
                + "\n环境\n"
                + "  Python arcpy: " + DescribirPython27() + "\n"
                + "  日志:         " + Log.PathInfo + "\n"
                + "\n现在打开日志文件？";

            if (MessageBox.Show(texto, "yghsBridge · 桥接状态",
                                MessageBoxButtons.YesNo, MessageBoxIcon.Information) == DialogResult.Yes)
            {
                AbrirLog();
            }
        }

        private static string DescribirDocumento()
        {
            try
            {
                var app = Handlers.ArcSession.App();
                var doc = app.Document as ESRI.ArcGIS.ArcMapUI.IMxDocument;
                if (doc == null) return "(无文档)";
                string mapa = doc.FocusMap != null ? doc.FocusMap.Name : "?";
                int capas = doc.FocusMap != null ? doc.FocusMap.LayerCount : 0;
                return app.Document.Title + "  ·  地图 " + mapa + "，" + capas + " 个图层";
            }
            catch (Exception ex)
            {
                return "(不可访问: " + ex.Message + ")";
            }
        }

        /// <summary>与 runner 相同：先看环境变量，再看标准安装。没有它就没有 execute_arcpy 与 DDP。</summary>
        private static string DescribirPython27()
        {
            string exe = Environment.GetEnvironmentVariable("ARCMAP_PYTHON27");
            if (string.IsNullOrEmpty(exe)) exe = @"C:\Python27\ArcGIS10.5\python.exe";
            return File.Exists(exe) ? exe : "未找到 (" + exe + ")";
        }

        private static void AbrirLog()
        {
            try
            {
                if (File.Exists(Log.PathInfo))
                    Process.Start(new ProcessStartInfo { FileName = Log.PathInfo, UseShellExecute = true });
                else
                    MessageBox.Show("暂无日志文件 " + Log.PathInfo,
                                    "yghsBridge · 桥接状态");
            }
            catch (Exception ex)
            {
                MessageBox.Show("无法打开日志：\n" + ex.Message,
                                "yghsBridge · 桥接状态");
            }
        }
    }

    /// <summary>
    /// 打开/关闭「消息面板」（可停靠日志窗口），点一下开、再点一下收。
    /// 对齐 Pro 插件的 ShowLogButton。
    /// </summary>
    public class ShowLogButton : AddInButton
    {
        protected override void OnClick()
        {
            BridgeLogDockableWindow.Toggle();
        }

        protected override void OnUpdate()
        {
            Enabled = true;
            Checked = BridgeLogDockableWindow.IsVisible;
        }
    }

    /// <summary>
    /// 自动启动桥接，做成**下拉框**而非按钮：按钮图标无法热切换（add-in 的 Button
    /// 类只暴露 Caption/Message/Tooltip/Enabled/Checked），而 Checked 的按下态在
    /// 工具栏上读起来不明显。下拉框用文字直接显示当前值，一目了然，无需额外配置。
    /// </summary>
    public class AutoStartComboBox : AddInComboBox
    {
        private const string TextoNo = "自动启动: 否";
        private const string TextoSi = "自动启动: 是";

        private readonly int _cookieNo;
        private readonly int _cookieSi;
        private bool _sincronizando;

        public AutoStartComboBox()
        {
            // 列表是封闭的（Config.xml 里 editable="false"）：只有两个值。
            _cookieNo = Add(TextoNo);
            _cookieSi = Add(TextoSi);
            SincronizarConPreferencia();
        }

        /// <summary>把下拉框显示值对齐注册表偏好，但不触发 OnSelChange（那会再写一次偏好）。</summary>
        private void SincronizarConPreferencia()
        {
            _sincronizando = true;
            try { Select(Ajustes.Autoarranque ? _cookieSi : _cookieNo); }
            finally { _sincronizando = false; }
        }

        protected override void OnSelChange(int cookie)
        {
            if (_sincronizando || cookie < 0) return;

            bool activar = (cookie == _cookieSi);
            Ajustes.Autoarranque = activar;

            string aviso;
            if (activar)
            {
                // 立即生效：选择自动启动时，本次会话桥接也应已处于监听状态，而非等下次。
                string error = McpExtension.Instance != null ? McpExtension.Instance.StartServer() : null;
                aviso =
                    "自动启动已开启。\n\n"
                    + "每次打开 ArcMap 时桥接服务都会自动启动。\n"
                    + (error == null
                        ? "本次会话已在监听 127.0.0.1:" + McpServer.Port + "。"
                        : "提示：当前无法立即启动：\n" + error);
            }
            else
            {
                aviso =
                    "自动启动已关闭。\n\n"
                    + "下次会话起需手动点击「启动桥接」。\n"
                    + "当前桥接仍保持运行，直到你手动停止。";
            }

            // MessageBox 不能在这里面弹：关闭模态对话框时，ArcMap 的 ComboBox 会
            // 把选择还原到第一项并再次触发 OnSelChange（变成「否」），覆盖刚保存的偏好。
            // 所以推迟到 message pump 之后执行，同时保持 _sincronizando 为 true，
            // 以忽略期间任何虚假的重复触发。
            _sincronizando = true;
            StaDispatcher.Post(delegate
            {
                try
                {
                    MessageBox.Show(aviso, "yghsBridge · 自动启动");
                    // 按注册表重申可见文本，以防对话框循环试图还原选择。
                    Select(Ajustes.Autoarranque ? _cookieSi : _cookieNo);
                }
                finally { _sincronizando = false; }
            });
        }

        protected override void OnUpdate()
        {
            Enabled = true;
        }
    }


}
