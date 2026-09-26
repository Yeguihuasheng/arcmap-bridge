using System;
using System.IO;

namespace YghsBridge.AddIn
{
    /// <summary>
    /// 文件日志：无 Visual Studio 就没有调试器——日志就是调试器。
    /// 技术日志（INFO/ERROR）只进文件 + 以 [技术] 前缀进面板（便于现场排障）；
    /// 用户可见的「人话」请走 BridgeLog.Note()，别直接调 Log.Info。
    /// </summary>
    internal static class Log
    {
        private static readonly object _lock = new object();
        private static readonly string _path = InitPath();

        public static string PathInfo
        {
            get { return _path; }
        }

        private static string InitPath()
        {
            try
            {
                Directory.CreateDirectory(@"C:\MCP_Logs");
                return @"C:\MCP_Logs\yghs-bridge.log";
            }
            catch
            {
                return Path.Combine(Path.GetTempPath(), "yghs-bridge.log");
            }
        }

        public static void Info(string msg)
        {
            WriteLine("INFO ", msg);
        }

        public static void Error(string msg, Exception ex = null)
        {
            Estadisticas.RegistrarError(); // el contador que ve el botón "Estado"
            WriteLine("ERROR", ex == null ? msg : msg + " :: " + ex);
        }

        private static void WriteLine(string level, string msg)
        {
            try
            {
                lock (_lock)
                {
                    File.AppendAllText(_path,
                        DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff")
                        + " [" + level + "] " + msg + Environment.NewLine);
                }
            }
            catch
            {
                // El log jamás tira ArcMap.
            }

            // 技术日志进面板（以 [技术] 前缀区分于 Note() 的人话），方便现场排障。
            // 但 Note() 写文件留档用的 "[面板] " 前缀行**不再镜像进面板**——它本身就是
            // 面板人话行的文件对照，再镜像会造成每条人话在面板里出现两次。
            try
            {
                if (!msg.StartsWith("[面板] "))
                {
                    BridgeLog.Append(DateTime.Now.ToString("MM-dd HH:mm:ss") + "  [技术] "
                        + level.Trim() + "  " + msg);
                }
            }
            catch
            {
                // 若 BridgeLog 尚未初始化（静态构造顺序），忽略即可，不影响文件日志。
            }
        }
    }
}
