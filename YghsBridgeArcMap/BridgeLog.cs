using System;
using System.Collections.Generic;

namespace YghsBridge.AddIn
{
    /// <summary>
    /// 进程内环形日志缓冲（对齐 Pro 插件 BridgeLog 的语义），消息面板的唯一数据源。
    ///
    /// 两个出口，各司其职：
    ///   · <see cref="Append"/> —— 技术日志（排障用，带 INFO/ERROR 级别），面板里以 [技术] 前缀呈现；
    ///   · <see cref="Note"/>  —— 用户可见「人话」（带 ✅/❌/⇒/│ 图标、MM-dd 短时间戳、超长截断、样板噪音过滤）。
    ///
    /// 线程安全：socket/后台线程写，UI 线程读（面板）。
    /// </summary>
    internal static class BridgeLog
    {
        private const int MaxLineas = 2000;              // 面板内存上限，防长时间会话胀内存
        private const int NotaMaxLargo = 200;            // 单条「人话」上限，超长截断（对齐 Pro 的 Note）
        private static readonly object _lock = new object();
        private static readonly List<string> _lineas = new List<string>();

        /// <summary>面板追加一行时触发（在 UI 线程外调用也会被安全调度）。</summary>
        public static event Action<string> Appended;

        /// <summary>历史快照，供面板视图构造时补全。末尾补换行，避免与后续追加行粘连。</summary>
        public static string Snapshot()
        {
            lock (_lock)
            {
                if (_lineas.Count == 0) return string.Empty;
                // 末尾必须带换行：面板构造时用 Text 灌入快照，之后 AppendText 追加
                // 增量；快照末行若无换行，第一条新日志会直接粘在末行尾部。
                return string.Join(Environment.NewLine, _lineas.ToArray()) + Environment.NewLine;
            }
        }

        /// <summary>
        /// 追加一行原始内容（可从任意线程调用）。不截断、不过滤——这是技术日志出口。
        /// 已带时间戳的 line 原样进面板，避免二次加戳。
        /// </summary>
        public static void Append(string line)
        {
            if (line == null) return;
            Push(line);
        }

        /// <summary>
        /// 用户可见「人话」通知（对齐 Pro 的 BridgeServer.Note）：
        ///   1. 超长截断（&gt;200 字符截为「…（详见日志）」）
        ///   2. 加 MM-dd HH:mm:ss 短时间戳
        ///   3. 写进面板（通过 Append）+ 文件日志（Log.Info）
        /// 图标（✅/❌/⇒/│）由调用方在 msg 里自带，本方法只负责格式与出口。
        /// </summary>
        public static void Note(string msg)
        {
            if (string.IsNullOrEmpty(msg)) return;
            string cuerpo = msg;
            if (cuerpo.Length > NotaMaxLargo)
                cuerpo = cuerpo.Substring(0, NotaMaxLargo) + " …（详见日志）";

            string stamped = DateTime.Now.ToString("MM-dd HH:mm:ss") + "  " + cuerpo;
            Push(stamped);

            // 文件日志留一份完整对照（不截断），供排障回溯。
            Log.Info("[面板] " + msg);
        }

        /// <summary>把一行压入环形缓冲并广播给面板。</summary>
        private static void Push(string line)
        {
            lock (_lock)
            {
                _lineas.Add(line);
                if (_lineas.Count > MaxLineas)
                    _lineas.RemoveRange(0, _lineas.Count - MaxLineas);
            }

            Action<string> h = Appended;
            if (h != null)
            {
                foreach (Action<string> d in h.GetInvocationList())
                {
                    try { d(line); }
                    catch { /* 面板收不收得到，都不该影响日志本身 */ }
                }
            }
        }
    }
}
