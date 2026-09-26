using System;

namespace YghsBridge.AddIn
{
    /// <summary>
    /// 更新检查（已停用）。保留类型与属性以兼容 Diagnostico/McpExtension 的引用：
    /// 不再访问任何网络地址，HayNueva 恒为 false。
    /// </summary>
    internal static class Actualizaciones
    {
        public const string RepoUrl = "";
        public const string ActualizarUrl = "";

        /// <summary>Última versión conocida (de red o de caché), sin la "v". Para el indicador.</summary>
        public static string UltimaDisponible { get; private set; }

        /// <summary>¿La última conocida es mayor que la instalada?</summary>
        public static bool HayNueva { get; private set; }

        /// <summary>Versión instalada, desde el ensamblado.</summary>
        public static Version VersionActual()
        {
            return typeof(Actualizaciones).Assembly.GetName().Version;
        }

        /// <summary>已停用：直接返回，不做任何网络请求。</summary>
        public static void ComprobarEnSegundoPlano(Action<string> avisar)
        {
        }

        /// <summary>已停用：恒返回 null。</summary>
        public static Version ConsultarUltima()
        {
            return null;
        }
    }
}
