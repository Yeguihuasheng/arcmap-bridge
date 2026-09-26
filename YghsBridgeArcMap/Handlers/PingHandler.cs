using System;
using System.Threading;
using ESRI.ArcGIS.ArcMapUI;
using ESRI.ArcGIS.Framework;
using Newtonsoft.Json.Linq;

namespace YghsBridge.AddIn.Handlers
{
    /// <summary>
    /// Latido del puente: confirma que el add-in responde desde el hilo STA y
    /// devuelve un vistazo de la sesión (documento, mapa activo, nº de capas).
    /// </summary>
    internal static class PingHandler
    {
        public static JObject Run(JObject parameters)
        {
            JObject result = new JObject();
            // Versión leída del ensamblado (el <Version> del csproj): no se queda obsoleta.
            Version v = typeof(PingHandler).Assembly.GetName().Version;
            result["addin"] = "yghsBridge " + v.ToString(3) + " (.NET)";
            result["thread"] = Thread.CurrentThread.ManagedThreadId;
            result["apartment"] = Thread.CurrentThread.GetApartmentState().ToString();

            try
            {
                IApplication app = ArcSession.App();
                result["application"] = app.Caption;

                IMxDocument doc = app.Document as IMxDocument;
                if (doc != null)
                {
                    result["document"] = app.Document.Title;
                    result["focus_map"] = doc.FocusMap != null ? doc.FocusMap.Name : null;
                    result["layer_count"] = doc.FocusMap != null ? doc.FocusMap.LayerCount : 0;
                }
            }
            catch (Exception ex)
            {
                // El ping no falla por esto: reporta el problema y sigue.
                result["arcobjects_warning"] = "无法访问 ArcObjects：" + ex.Message;
            }
            return Protocol.Result(result);
        }
    }
}
