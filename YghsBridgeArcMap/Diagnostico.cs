using System;
using System.IO;
using Microsoft.Win32;

namespace YghsBridge.AddIn
{
    /// <summary>
    /// Texto de diagnóstico NO SENSIBLE, reutilizado por el botón Estado y por el
    /// reporte de problemas. Deliberadamente NO incluye el título del documento ni
    /// nombres de capas ni rutas: eso son posibles datos de cliente (restricción L3)
    /// y el reporte sale de la máquina. Solo entorno, versiones y contadores.
    /// </summary>
    internal static class Diagnostico
    {
        /// <summary>Versión del add-in leída del ensamblado (patrón usado en toda la UI).</summary>
        public static string VersionAddin()
        {
            return typeof(Diagnostico).Assembly.GetName().Version.ToString(3);
        }

        /// <summary>Bloque de diagnóstico sin datos de cliente. Cada dato va en su
        /// propio try: un entorno raro nunca debe impedir generar el reporte.</summary>
        public static string TextoNoSensible(bool puenteActivo)
        {
            return
                "yghsBridge:   " + VersionAddin() + " (.NET)\r\n"
                + "ArcMap:       " + VersionArcMap() + "\r\n"
                + "系统:         " + DescribirSO() + "\r\n"
                + ".NET CLR:     " + Environment.Version + "\r\n"
                + "桥接:         " + (puenteActivo ? "运行中" : "已停止")
                    + " (127.0.0.1:" + McpServer.Port + ")\r\n"
                + "更新检查:     " + " " + DescribirActualizacion() + "\r\n"
                + "会话开始:     " + Estadisticas.Inicio.ToString("yyyy-MM-dd HH:mm:ss") + "\r\n"
                + "请求数:       " + Estadisticas.Peticiones + "\r\n"
                + "错误数:       " + Estadisticas.Errores + "\r\n"
                + "最近命令:     " + Estadisticas.UltimoComando + "\r\n"
                + "Python arcpy: " + DescribirPython27();
        }

        /// <summary>Estado de actualización en una línea, para colar en Estado/reporte.</summary>
        public static string DescribirActualizacion()
        {
            if (Actualizaciones.HayNueva)
                return "有 v" + Actualizaciones.UltimaDisponible + " 可用";
            if (!string.IsNullOrEmpty(Actualizaciones.UltimaDisponible))
                return "已是最新（最近检查版本 v" + Actualizaciones.UltimaDisponible + ")";
            return "尚未检查";
        }

        /// <summary>Versión real de ArcGIS Desktop desde el registro (best-effort).
        /// Evita arrastrar ESRI.ArcGIS.Version solo para esto.</summary>
        public static string VersionArcMap()
        {
            foreach (string ruta in new[]
            {
                @"SOFTWARE\Wow6432Node\ESRI\ArcGIS",
                @"SOFTWARE\ESRI\ArcGIS"
            })
            {
                try
                {
                    using (RegistryKey k = Registry.LocalMachine.OpenSubKey(ruta))
                    {
                        if (k == null) continue;
                        object v = k.GetValue("RealVersion") ?? k.GetValue("Version");
                        if (v != null) return v.ToString();
                    }
                }
                catch { }
            }
            return "10.x（注册表中未检测到）";
        }

        private static string DescribirSO()
        {
            try
            {
                return Environment.OSVersion.VersionString
                       + (Environment.Is64BitOperatingSystem ? " (x64)" : " (x86)");
            }
            catch { return "（未知）"; }
        }

        /// <summary>Mismo criterio que el runner: variable de entorno y, si no, la
        /// instalación estándar. Sin él no hay execute_arcpy ni DDP.</summary>
        public static string DescribirPython27()
        {
            try
            {
                string exe = Environment.GetEnvironmentVariable("ARCMAP_PYTHON27");
                if (string.IsNullOrEmpty(exe)) exe = @"C:\Python27\ArcGIS10.5\python.exe";
                return File.Exists(exe) ? exe : "未找到（" + exe + ")";
            }
            catch { return "（无法检测）"; }
        }
    }
}
