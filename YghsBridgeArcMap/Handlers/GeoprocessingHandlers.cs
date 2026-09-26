using System;
using System.Collections.Generic;
using ESRI.ArcGIS.ArcMapUI;
using ESRI.ArcGIS.Carto;
using ESRI.ArcGIS.Geoprocessing;
using ESRI.ArcGIS.esriSystem;
using Newtonsoft.Json.Linq;

namespace YghsBridge.AddIn.Handlers
{
    /// <summary>
    /// run_geoprocessing — NATIVO por IGeoProcessor2 sobre la sesión viva:
    /// conserva la semántica de capas de la TOC con definition query y selección,
    /// que el subprocess no puede dar. Contrato JSON de los schemas del servidor
    /// MCP. Corre en STA con el timeout largo; un GP pesado congela la GUI
    /// (limitación conocida — para análisis pesados están las tools ambientales,
    /// que van out-of-process).
    /// </summary>
    internal static class GeoprocessingHandlers
    {
        // Guard de resolución: strings con pinta de ruta o de SQL no se resuelven
        // a capa (un nombre de campo o keyword que coincida se sustituiría en silencio).
        private static readonly char[] NoResolver = "\\/:*?\"<>|='".ToCharArray();

        // Módulo arcpy -> alias de toolbox del GeoProcessor: coinciden salvo ddd.
        private static string AliasToolbox(string moduloArcpy)
        {
            return string.Equals(moduloArcpy, "ddd", StringComparison.OrdinalIgnoreCase)
                ? "3d" : moduloArcpy;
        }

        /// <summary>Checkout best-effort de la extensión que el toolbox necesita
        /// (equivalente .NET del checkout de extensiones de arcpy). Si falla,
        /// Execute dará su propio error de licencia y se devuelve tal cual.</summary>
        private static void CheckoutSiHaceFalta(string alias)
        {
            esriLicenseExtensionCode codigo;
            if (string.Equals(alias, "sa", StringComparison.OrdinalIgnoreCase))
                codigo = esriLicenseExtensionCode.esriLicenseExtensionCodeSpatialAnalyst;
            else if (string.Equals(alias, "3d", StringComparison.OrdinalIgnoreCase))
                codigo = esriLicenseExtensionCode.esriLicenseExtensionCode3DAnalyst;
            else
                return;
            try
            {
                IAoInitialize lic = new AoInitializeClass();
                if (!lic.IsExtensionCheckedOut(codigo))
                    lic.CheckOutExtension(codigo);
            }
            catch (Exception ex)
            {
                Log.Info("检出扩展 '" + alias + "' 失败（仍将尝试执行 GP）：" + ex.Message);
            }
        }

        public static JObject RunGeoprocessing(JObject parameters)
        {
            string tool = (string)parameters["tool"];
            if (string.IsNullOrEmpty(tool))
                throw new ArgumentException(
                    "请提供 'tool'（如 'management.CopyFeatures' 或 'Buffer_analysis'）。");
            JArray args = parameters["params"] as JArray ?? new JArray();
            bool resolverCapas = parameters["resolver_capas"] == null
                || parameters["resolver_capas"].Type == JTokenType.Null
                || (bool)parameters["resolver_capas"];

            // Forma punteada estilo arcpy (management.GetCount) -> nombre GP (GetCount_management).
            string nombreGp = tool;
            string alias = null;
            int punto = tool.IndexOf('.');
            if (punto > 0)
            {
                alias = AliasToolbox(tool.Substring(0, punto));
                nombreGp = tool.Substring(punto + 1) + "_" + alias;
            }
            else
            {
                int guion = tool.LastIndexOf('_');
                if (guion > 0)
                    alias = tool.Substring(guion + 1);
            }
            if (alias != null)
                CheckoutSiHaceFalta(alias);

            // Capas de la TOC disponibles para la resolución de nombres (gotcha
            // ERROR 000732 de arcpy fuera de la ventana interactiva: el GP no
            // resuelve nombres de capa por sí solo; pasar el objeto Layer honra
            // además su definition query y selección).
            var capas = new List<ILayer>();
            if (resolverCapas)
            {
                IMxDocument doc;
                IMap map = MapHandlers.FocusMap(out doc);
                IEnumLayer enumLayer = map.get_Layers(null, true);
                enumLayer.Reset();
                ILayer lyr;
                while ((lyr = enumLayer.Next()) != null)
                    capas.Add(lyr);
            }

            IVariantArray valores = new VarArrayClass();
            foreach (JToken a in args)
                valores.Add(ResolverArg(a, resolverCapas, capas));

            IGeoProcessor2 gp = new GeoProcessorClass();
            gp.AddOutputsToMap = true; // mismo comportamiento que arcpy dentro de ArcMap
            ESRI.ArcGIS.esriSystem.ITrackCancel cancel =
                (ESRI.ArcGIS.esriSystem.ITrackCancel)new ESRI.ArcGIS.Display.CancelTrackerClass();

            IGeoProcessorResult resultado;
            try
            {
                resultado = gp.Execute(nombreGp, valores, cancel);
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException(
                    "地理处理 '" + tool + "' 失败：" + ex.Message + ". GP 消息：" + Mensajes(gp), ex);
            }

            var salidas = new JArray();
            try
            {
                for (int i = 0; i < resultado.OutputCount; i++)
                {
                    ESRI.ArcGIS.Geodatabase.IGPValue v = resultado.GetOutput(i);
                    salidas.Add(v != null ? v.GetAsText() : null);
                }
            }
            catch { /* salidas best-effort */ }

            return Protocol.Result(new JObject
            {
                ["tool"] = tool,
                ["salidas"] = salidas,
                ["mensajes"] = Mensajes(gp),
            });
        }

        /// <summary>calculate_geometry — NATIVO vía GeoProcessor in-process
        /// (contrato JSON de los schemas del servidor MCP). NO puede ir por
        /// subprocess: la sesión viva mantiene un schema lock sobre toda fuente
        /// cargada en la TOC y AddGeometryAttributes necesita añadir campos.
        /// In-process no hay conflicto y pasar el Layer honra def. query y selección.</summary>
        public static JObject CalculateGeometry(JObject parameters)
        {
            string entrada = (string)(parameters["entrada"] ?? parameters["capa"]);
            JToken props = parameters["propiedades"];
            if (string.IsNullOrEmpty(entrada) || props == null || props.Type == JTokenType.Null)
                throw new ArgumentException("请提供 'entrada'（图层或要素类）和 'propiedades'。");
            string propiedades = props.Type == JTokenType.Array
                ? string.Join(";", ((JArray)props).ToObject<string[]>())
                : (string)props;
            string unidadLongitud = (string)parameters["unidad_longitud"] ?? "";
            string unidadArea = (string)parameters["unidad_area"] ?? "";
            string crs = (string)parameters["crs"] ?? "";

            var gpParams = new JObject
            {
                ["tool"] = "management.AddGeometryAttributes",
                ["params"] = new JArray { entrada, propiedades, unidadLongitud, unidadArea, crs },
                // la resolución de capas usa el guard de arriba; una ruta no se toca
                ["resolver_capas"] = true,
            };
            JObject r = RunGeoprocessing(gpParams);
            if (!(bool)r["ok"])
                return r;
            return Protocol.Result(new JObject
            {
                ["entrada"] = entrada,
                ["propiedades"] = propiedades,
                ["unidad_longitud"] = unidadLongitud,
                ["unidad_area"] = unidadArea,
            });
        }

        private static object ResolverArg(JToken a, bool resolverCapas, List<ILayer> capas)
        {
            switch (a.Type)
            {
                case JTokenType.Integer: return (long)a;
                case JTokenType.Float: return (double)a;
                case JTokenType.Boolean: return (bool)a;
                case JTokenType.Null: return "";
                case JTokenType.String:
                    string s = (string)a;
                    if (resolverCapas && s.IndexOfAny(NoResolver) < 0)
                    {
                        foreach (ILayer lyr in capas)
                            if (string.Equals(lyr.Name, s, StringComparison.OrdinalIgnoreCase))
                                return lyr;
                    }
                    return s;
                default:
                    return a.ToString();
            }
        }

        private static string Mensajes(IGeoProcessor2 gp)
        {
            try
            {
                object severidad = 0;
                return gp.GetMessages(ref severidad);
            }
            catch
            {
                return "";
            }
        }
    }
}
