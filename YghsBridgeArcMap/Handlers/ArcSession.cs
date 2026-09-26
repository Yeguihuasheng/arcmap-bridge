using System;
using System.IO;
using ESRI.ArcGIS.ArcMapUI;
using ESRI.ArcGIS.Framework;

namespace YghsBridge.AddIn.Handlers
{
    /// <summary>
    /// Acceso a la sesión viva de ArcMap. AppRef solo es co-creable DENTRO del
    /// proceso de ArcMap; co-crear vía ProgID y castear SOLO al interfaz (el cast
    /// al RCW de clase falla por identidad de tipos del singleton COM).
    /// Llamar siempre desde el hilo STA.
    /// </summary>
    internal static class ArcSession
    {
        public static IApplication App()
        {
            object appRef = Activator.CreateInstance(Type.GetTypeFromProgID("esriFramework.AppRef"));
            return (IApplication)appRef;
        }

        public static IMxDocument Doc(IApplication app)
        {
            IMxDocument doc = app.Document as IMxDocument;
            if (doc == null)
                throw new InvalidOperationException("当前文档不是 ArcMap 文档（IMxDocument）。");
            return doc;
        }

        /// <summary>Ruta del .mxd abierto, o null si el documento NO está guardado.
        ///
        /// OJO (bug corregido 2026-09-26): el truco de ITemplates devuelve, para un
        /// documento "sin título", el fichero TEMPORAL de ArcMap
        /// (%TEMP%\arcXXXX\~DFxxxx.TMP). Ese TMP existe en disco, así que el puente
        /// creía poder copiar el .mxd del disco y acababa copiando un mapa INVÁLIDO:
        /// al abrirlo, pageLayout era null y toda operación de documento fallaba con
        /// "'NoneType' object has no attribute 'dataFrames'". Ahora solo se aceptan
        /// rutas .mxd reales; si no lo son, se devuelve null y el llamante serializa
        /// la sesión (SaveAsDocument), que sí produce un mapa legible.</summary>
        public static string MxdPath(IApplication app)
        {
            // Truco ITemplates (mismo que get_arcmap_info), con filtro de .mxd real.
            // (ArcObjects IDocument no expone FullName, así que no hay vía directa.)
            try
            {
                ESRI.ArcGIS.Framework.ITemplates templates = app.Templates;
                if (templates != null && templates.Count > 0)
                {
                    string ruta = templates.get_Item(templates.Count - 1);
                    if (EsMxdReal(ruta))
                        return ruta;
                }
            }
            catch { }

            return null;
        }

        /// <summary>¿Es un .mxd de verdad en disco? Descarta el TMP de la sesión
        /// (~DFxxxx.TMP) y cualquier cosa que no sea un mapa guardado.</summary>
        private static bool EsMxdReal(string ruta)
        {
            return !string.IsNullOrEmpty(ruta)
                && ruta.EndsWith(".mxd", StringComparison.OrdinalIgnoreCase)
                && File.Exists(ruta);
        }
    }
}
