using System;
using System.IO;
using ESRI.ArcGIS.ArcMapUI;
using ESRI.ArcGIS.Carto;
using ESRI.ArcGIS.Display;
using ESRI.ArcGIS.esriSystem;
using ESRI.ArcGIS.Framework;
using ESRI.ArcGIS.Geometry;
using ESRI.ArcGIS.Output;
using Newtonsoft.Json.Linq;

namespace YghsBridge.AddIn.Handlers
{
    /// <summary>
    /// get_canvas_screenshot — renderiza la vista (o el layout) a PNG y devuelve
    /// la imagen en base64; el servidor MCP la convierte en imagen inline
    /// (lee result.imagen_b64).
    /// El dibujado pasa por ITrackCancel (CancelTracker): ESC en ArcMap aborta
    /// un render largo sin matar el puente.
    /// </summary>
    internal static class ScreenshotHandler
    {
        private const double ScreenDpi = 96.0;

        public static JObject Run(JObject parameters)
        {
            string modo = ((string)parameters["modo"] ?? "vista").ToLowerInvariant();
            int dpi = parameters["dpi"] != null ? (int)parameters["dpi"] : 96;
            if (dpi < 24) dpi = 24;

            IApplication app = ArcSession.App();
            IMxDocument doc = ArcSession.Doc(app);

            // IActiveView.Output solo dibuja con garantías la vista ACTIVA (la que
            // tiene ScreenDisplay); si piden la otra, se exporta la activa y se avisa.
            bool layoutActivo = doc.ActiveView is IPageLayout;
            bool quierenLayout = modo == "layout";
            string aviso = null;
            if (quierenLayout != layoutActivo)
            {
                aviso = "请求的视图（'" + modo + "'）不是当前活动视图；将导出活动视图（"
                        + (layoutActivo ? "layout" : "vista") + "）。如需另一个，请在 ArcMap 中切换视图。";
                modo = layoutActivo ? "layout" : "vista";
            }
            IActiveView av = doc.ActiveView;

            string tmp = System.IO.Path.Combine(System.IO.Path.GetTempPath(),
                "yghsbridge_shot_" + Guid.NewGuid().ToString("N") + ".png");
            byte[] raw;
            try
            {
                IExport export = new ExportPNGClass();
                export.ExportFileName = tmp;
                export.Resolution = dpi;

                tagRECT frame = av.ExportFrame;
                double escala = dpi / ScreenDpi;
                var outRect = new tagRECT
                {
                    left = 0,
                    top = 0,
                    right = (int)Math.Round((frame.right - frame.left) * escala),
                    bottom = (int)Math.Round((frame.bottom - frame.top) * escala)
                };
                IEnvelope pixelBounds = new EnvelopeClass();
                pixelBounds.PutCoords(0, 0, outRect.right, outRect.bottom);
                export.PixelBounds = pixelBounds;

                ITrackCancel cancel = new CancelTrackerClass();
                cancel.CancelOnKeyPress = true;
                cancel.CancelOnClick = false;

                int hdc = export.StartExporting();
                try
                {
                    av.Output(hdc, dpi, ref outRect, null, cancel);
                }
                finally
                {
                    export.FinishExporting();
                    export.Cleanup();
                }

                if (!cancel.Continue())
                    throw new OperationCanceledException("用户已取消渲染（在 ArcMap 中按 ESC）。");

                raw = File.ReadAllBytes(tmp);
            }
            finally
            {
                try { File.Delete(tmp); } catch { }
            }

            var result = new JObject
            {
                ["modo"] = modo,
                ["dpi"] = dpi,
                ["bytes"] = raw.Length,
                ["imagen_b64"] = Convert.ToBase64String(raw)
            };
            if (aviso != null)
                result["aviso"] = aviso;
            return Protocol.Result(result);
        }
    }
}
