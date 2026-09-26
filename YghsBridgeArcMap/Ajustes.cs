using System;
using Microsoft.Win32;

namespace YghsBridge.AddIn
{
    /// <summary>
    /// Preferencias del add-in, persistidas por usuario en el registro
    /// (HKCU\Software\yghsbridge\yghsBridge). Se usa el registro y no un fichero de
    /// configuración porque el add-in se instala en una carpeta versionada por GUID:
    /// al actualizar la versión, un fichero junto a la DLL se perdería.
    /// </summary>
    internal static class Ajustes
    {
        private const string Clave = @"Software\yghsbridge\yghsBridge";
        private const string ValorAutoarranque = "Autoarranque";
        private const string ValorUltimaComprobacion = "UltimaComprobacion";
        private const string ValorUltimaVersionVista = "UltimaVersionVista";
        private const string ValorVersionAvisada = "VersionAvisada";

        /// <summary>¿Debe levantarse el puente solo al abrir ArcMap? (por defecto, no)</summary>
        public static bool Autoarranque
        {
            get
            {
                try
                {
                    using (RegistryKey k = Registry.CurrentUser.OpenSubKey(Clave))
                    {
                        if (k == null) return false;
                        object v = k.GetValue(ValorAutoarranque);
                        return v != null && Convert.ToInt32(v) != 0;
                    }
                }
                catch (Exception ex)
                {
                    Log.Error("无法读取自动启动偏好", ex);
                    return false;
                }
            }
            set
            {
                try
                {
                    using (RegistryKey k = Registry.CurrentUser.CreateSubKey(Clave))
                        k.SetValue(ValorAutoarranque, value ? 1 : 0, RegistryValueKind.DWord);

                    // Se relee para confirmar que quedo escrito de verdad: una
                    // preferencia que dice guardarse y no persiste es peor que un error.
                    bool comprobado = Autoarranque;
                    Log.Info("自动启动已保存为 " + (value ? "是" : "否")
                             + "，写入 HKCU\\" + Clave + "（回读：" + (comprobado ? "是" : "否") + ")");
                    if (comprobado != value)
                        Log.Error("自动启动偏好未能持久化到注册表。");
                }
                catch (Exception ex)
                {
                    Log.Error("无法保存自动启动偏好", ex);
                }
            }
        }

        // --- Caché de la comprobación de actualizaciones (ver Actualizaciones.cs) ---
        // Strings simples: fecha de la última comprobación (para no consultar la red más
        // de 1×/día), última versión vista y versión para la que ya se mostró el aviso.

        /// <summary>Fecha (yyyy-MM-dd) de la última consulta a GitHub, o "" si nunca.</summary>
        public static string UltimaComprobacion
        {
            get { return LeerCadena(ValorUltimaComprobacion); }
            set { EscribirCadena(ValorUltimaComprobacion, value); }
        }

        /// <summary>Última versión vista en GitHub (string Version), o "" si nunca.</summary>
        public static string UltimaVersionVista
        {
            get { return LeerCadena(ValorUltimaVersionVista); }
            set { EscribirCadena(ValorUltimaVersionVista, value); }
        }

        /// <summary>Versión para la que ya se mostró el aviso una vez (para no repetir).</summary>
        public static string VersionAvisada
        {
            get { return LeerCadena(ValorVersionAvisada); }
            set { EscribirCadena(ValorVersionAvisada, value); }
        }

        private static string LeerCadena(string valor)
        {
            try
            {
                using (RegistryKey k = Registry.CurrentUser.OpenSubKey(Clave))
                {
                    if (k == null) return "";
                    return k.GetValue(valor) as string ?? "";
                }
            }
            catch { return ""; }
        }

        private static void EscribirCadena(string valor, string contenido)
        {
            try
            {
                using (RegistryKey k = Registry.CurrentUser.CreateSubKey(Clave))
                    k.SetValue(valor, contenido ?? "", RegistryValueKind.String);
            }
            catch (Exception ex)
            {
                Log.Error("无法保存偏好 '" + valor + "'", ex);
            }
        }
    }
}
