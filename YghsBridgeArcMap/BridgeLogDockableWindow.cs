using System;
using System.Windows.Forms;
using System.Drawing;
using ESRI.ArcGIS.Framework;
using ESRI.ArcGIS.esriSystem;

namespace YghsBridge.AddIn
{
    /// <summary>
    /// 「yghsBridge」可停靠消息面板（对齐 Pro 插件的 BridgeLogPane / DockPane）：
    /// 一个 ArcMap 内可停靠的窗口，承载只读 TextBox 实时滚动日志。
    ///
    /// ArcMap AddIn 的可停靠窗口正确基类是 ESRI.ArcGIS.Desktop.AddIns.DockableWindow
    /// （不是 IDockableWindowDef——那是不进 AddIn 框架的底层 COM 接口）。宿主类在
    /// Config.xml 的 &lt;DockableWindows&gt; 里声明，OnCreateChild() 返回子控件句柄。
    /// 外部通过 Show()/Toggle() 开关，按钮（ShowLogButton）调用。
    /// </summary>
    internal class BridgeLogDockableWindow : ESRI.ArcGIS.Desktop.AddIns.DockableWindow
    {
        /// <summary>与 Config.xml 里 DockableWindow 的 id 一致（GetDockableWindow 用它定位）。</summary>
        public const string PanelId = "yghsbridge_MessagesPanel";

        private TextBox _box;

        public BridgeLogDockableWindow()
        {
            _box = new TextBox
            {
                Multiline = true,
                ReadOnly = true,
                WordWrap = false,
                ScrollBars = ScrollBars.Both,
                BackColor = Color.FromArgb(30, 30, 30),
                ForeColor = Color.FromArgb(220, 220, 220),
                Font = new Font("Consolas", 9.5f),
                Dock = DockStyle.Fill,
                Text = BridgeLog.Snapshot(),
            };
            _box.TextChanged += delegate { _box.SelectionStart = _box.TextLength; _box.ScrollToCaret(); };
            BridgeLog.Appended += Append;
        }

        protected override IntPtr OnCreateChild()
        {
            // 返回 TextBox 句柄，ArcMap 把它嵌入可停靠窗口。
            return _box.Handle;
        }

        protected override void Dispose(bool disposing)
        {
            try { BridgeLog.Appended -= Append; } catch { }
            if (disposing && _box != null)
            {
                try { _box.Dispose(); } catch { }
                _box = null;
            }
            base.Dispose(disposing);
        }

        /// <summary>追加一行（可从任意线程调用，内部安全调度到 UI 线程）。</summary>
        public void Append(string line)
        {
            if (line == null) return;
            try
            {
                if (_box != null && _box.IsHandleCreated && _box.InvokeRequired)
                    _box.BeginInvoke(new Action<string>(AppendCore), line);
                else
                    AppendCore(line);
            }
            catch { }
        }

        private void AppendCore(string line)
        {
            try
            {
                if (_box == null) return;
                if (_box.TextLength > 200000)                     // 防 TextBox 过长变卡
                    _box.Clear();
                _box.AppendText(line + Environment.NewLine);
                _box.SelectionStart = _box.TextLength;
                _box.ScrollToCaret();
            }
            catch { }
        }

        private static UID PanelUid()
        {
            return new UIDClass { Value = PanelId };
        }

        private static IDockableWindowManager Mgr()
        {
            var app = Handlers.ArcSession.App();
            return app as IDockableWindowManager;
        }

        /// <summary>打开（或激活）面板。返回是否成功。</summary>
        public static bool Show()
        {
            try
            {
                var mgr = Mgr();
                if (mgr == null) return false;
                var w = mgr.GetDockableWindow(PanelUid());
                if (w == null) return false;
                w.Show(true);
                return true;
            }
            catch { return false; }
        }

        /// <summary>面板开/关切换。</summary>
        public static bool Toggle()
        {
            try
            {
                var mgr = Mgr();
                if (mgr == null) return false;
                var w = mgr.GetDockableWindow(PanelUid());
                if (w == null) return false;
                w.Show(!w.IsVisible());
                return true;
            }
            catch { return false; }
        }

        /// <summary>面板当前是否可见（IDockableWindow.IsVisible）。</summary>
        public static bool IsVisible
        {
            get
            {
                try
                {
                    var mgr = Mgr();
                    if (mgr == null) return false;
                    var w = mgr.GetDockableWindow(PanelUid());
                    return w != null && w.IsVisible();
                }
                catch { return false; }
            }
        }
    }
}
