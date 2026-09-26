using System;
using ESRI.ArcGIS.Framework;
using Newtonsoft.Json.Linq;

namespace YghsBridge.AddIn.Handlers
{
    /// <summary>
    /// save_mxd / save_mxd_as — contrato JSON que esperan los schemas del servidor MCP.
    /// IApplication.SaveDocument(ruta) guarda en sitio; SaveAsDocument(ruta, true)
    /// equivale al mxd.saveACopy de arcpy (NO cambia el documento activo ni su ruta).
    /// </summary>
    internal static class DocumentHandlers
    {
        public static JObject SaveMxd(JObject parameters)
        {
            IApplication app = ArcSession.App();
            string ruta = ArcSession.MxdPath(app);
            if (string.IsNullOrEmpty(ruta) || !ruta.ToLowerInvariant().EndsWith(".mxd"))
                throw new InvalidOperationException(
                    "文档没有 .mxd 路径（是否从未保存？）。请使用 save_mxd_as。");
            app.SaveDocument(ruta);
            return Protocol.Result(new JObject { ["guardado"] = true, ["ruta"] = ruta });
        }

        public static JObject SaveMxdAs(JObject parameters)
        {
            string salida = (string)parameters["salida"];
            if (string.IsNullOrEmpty(salida))
                throw new ArgumentException("请提供 'salida'（目标 .mxd 路径）。");
            if (!salida.ToLowerInvariant().EndsWith(".mxd"))
                salida += ".mxd";

            IApplication app = ArcSession.App();
            string origen = ArcSession.MxdPath(app);
            app.SaveAsDocument(salida, true); // true = copia: el doc activo no cambia
            return Protocol.Result(new JObject
            {
                ["guardado"] = true,
                ["salida"] = salida,
                ["origen"] = origen
            });
        }
    }
}
