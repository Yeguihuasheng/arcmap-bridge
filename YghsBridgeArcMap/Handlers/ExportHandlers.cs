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
    /// export_pdf / export_jpg / export_view_png — contrato JSON que esperan los
    /// schemas del servidor MCP. Gotcha .NET vs arcpy: IActiveView.Output solo dibuja con
    /// garantías la vista ACTIVA (arcpy renderizaba el layout en frío), así que si
    /// la vista pedida no es la activa se CAMBIA temporalmente con el setter de
    /// IMxDocument.ActiveView y se restaura en finally. El dibujado pasa por
    /// ITrackCancel: ESC en ArcMap aborta sin matar el puente.
    /// </summary>
    internal static class ExportHandlers
    {
        private const double ScreenDpi = 96.0;

        public static JObject ExportPdf(JObject parameters)
        {
            string salida = RutaSalida(parameters, ".pdf");
            int dpi = parameters["dpi"] != null ? (int)parameters["dpi"] : 300;
            string aviso = Exportar(new ExportPDFClass(), salida, dpi, true, 0, 0);
            return Resultado(new JObject { ["salida"] = salida, ["dpi"] = dpi }, aviso);
        }

        public static JObject ExportJpg(JObject parameters)
        {
            string salida = RutaSalida(parameters, ".jpg");
            int dpi = parameters["dpi"] != null ? (int)parameters["dpi"] : 230;
            IExport export = new ExportJPEGClass();
            ((IExportJPEG)export).Quality = 95;
            string aviso = Exportar(export, salida, dpi, true, 0, 0);
            return Resultado(new JObject { ["salida"] = salida, ["dpi"] = dpi }, aviso);
        }

        public static JObject ExportViewPng(JObject parameters)
        {
            string salida = RutaSalida(parameters, ".png");
            int dpi = parameters["dpi"] != null ? (int)parameters["dpi"] : 150;
            string modo = ((string)parameters["modo"] ?? "vista").ToLowerInvariant();
            int ancho = parameters["ancho"] != null && parameters["ancho"].Type != JTokenType.Null
                ? (int)parameters["ancho"] : 0;
            int alto = parameters["alto"] != null && parameters["alto"].Type != JTokenType.Null
                ? (int)parameters["alto"] : 0;
            string aviso = Exportar(new ExportPNGClass(), salida, dpi, modo == "layout", ancho, alto);
            return Resultado(new JObject { ["salida"] = salida, ["dpi"] = dpi, ["modo"] = modo }, aviso);
        }

        private static JObject Resultado(JObject inner, string aviso)
        {
            if (aviso != null)
                inner["aviso"] = aviso;
            return Protocol.Result(inner);
        }

        private static string RutaSalida(JObject parameters, string extension)
        {
            string salida = (string)parameters["salida"];
            if (string.IsNullOrEmpty(salida))
                throw new ArgumentException("请提供 'salida'（目标文件路径）。");
            if (!salida.ToLowerInvariant().EndsWith(extension))
                salida += extension;
            string carpeta = System.IO.Path.GetDirectoryName(salida);
            if (!string.IsNullOrEmpty(carpeta) && !Directory.Exists(carpeta))
                throw new ArgumentException("输出文件夹不存在：" + carpeta);
            return salida;
        }

        /// <summary>
        /// Exporta la vista pedida (layout o data frame activo) a `salida`. Si esa
        /// vista no es la activa, cambia temporalmente y restaura al terminar.
        /// `anchoPx`/`altoPx` (solo PNG de vista) fuerzan el tamaño en píxeles; el
        /// que falte se deriva del aspect ratio del frame. Devuelve el aviso de
        /// cambio de vista, o null si no hubo cambio.
        /// </summary>
        private static string Exportar(IExport export, string salida, int dpi,
                                       bool quierenLayout, int anchoPx, int altoPx)
        {
            if (dpi < 24) dpi = 24;
            IApplication app = ArcSession.App();
            IMxDocument doc = ArcSession.Doc(app);

            bool layoutActivo = doc.ActiveView is IPageLayout;
            IActiveView original = doc.ActiveView;
            bool cambiada = false;
            string aviso = null;
            if (quierenLayout != layoutActivo)
            {
                doc.ActiveView = quierenLayout
                    ? (IActiveView)doc.PageLayout
                    : (IActiveView)doc.FocusMap;
                cambiada = true;
                aviso = "当前活动视图为 '" + (layoutActivo ? "layout" : "vista")
                        + "'；已临时切换为 '" + (quierenLayout ? "layout" : "vista")
                        + "' 以完成导出，随后已恢复。";
            }

            try
            {
                IActiveView av = doc.ActiveView;
                export.ExportFileName = salida;
                export.Resolution = dpi;

                tagRECT frame = av.ExportFrame;
                double frameAncho = frame.right - frame.left;
                double frameAlto = frame.bottom - frame.top;
                double escala = dpi / ScreenDpi;
                int outAncho = (int)Math.Round(frameAncho * escala);
                int outAlto = (int)Math.Round(frameAlto * escala);
                if (anchoPx > 0 && altoPx > 0) { outAncho = anchoPx; outAlto = altoPx; }
                else if (anchoPx > 0) { outAncho = anchoPx; outAlto = (int)Math.Round(anchoPx * frameAlto / frameAncho); }
                else if (altoPx > 0) { outAlto = altoPx; outAncho = (int)Math.Round(altoPx * frameAncho / frameAlto); }

                var outRect = new tagRECT { left = 0, top = 0, right = outAncho, bottom = outAlto };
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
                {
                    try { File.Delete(salida); } catch { }
                    throw new OperationCanceledException("用户已取消导出（在 ArcMap 中按 ESC）。");
                }
            }
            finally
            {
                if (cambiada)
                {
                    doc.ActiveView = original;
                    doc.ActiveView.Refresh();
                }
            }
            return aviso;
        }
    }
}
