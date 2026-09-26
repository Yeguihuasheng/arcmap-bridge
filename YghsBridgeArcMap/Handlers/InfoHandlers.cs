using System;
using ESRI.ArcGIS.ArcMapUI;
using ESRI.ArcGIS.Carto;
using ESRI.ArcGIS.Framework;
using ESRI.ArcGIS.Geodatabase;
using ESRI.ArcGIS.Geometry;
using Newtonsoft.Json.Linq;

namespace YghsBridge.AddIn.Handlers
{
    /// <summary>
    /// get_arcmap_info / list_layers / zoom_to_layer — contrato JSON que esperan
    /// los schemas del servidor MCP.
    /// </summary>
    internal static class InfoHandlers
    {
        public static JObject GetArcmapInfo(JObject parameters)
        {
            IApplication app = ArcSession.App();
            IMxDocument doc = ArcSession.Doc(app);

            // Ruta del .mxd: el último item de ITemplates es el documento actual.
            string mxdPath = null;
            try
            {
                ITemplates templates = app.Templates;
                if (templates != null && templates.Count > 0)
                    mxdPath = templates.get_Item(templates.Count - 1);
            }
            catch { /* documento sin guardar o Templates no disponible */ }

            var dataFrames = new JArray();
            IMaps maps = doc.Maps;
            for (int i = 0; i < maps.Count; i++)
                dataFrames.Add(maps.get_Item(i).Name);

            // La escala puede no estar definida según el estado del documento;
            // que no tumbe toda la llamada.
            double? escala = null;
            try
            {
                if (doc.FocusMap != null)
                    escala = doc.FocusMap.MapScale;
            }
            catch { }

            // Vista activa: nombre del data frame en vista de datos, o "PAGE_LAYOUT".
            string vistaActiva = doc.ActiveView is IPageLayout
                ? "PAGE_LAYOUT"
                : (doc.FocusMap != null ? doc.FocusMap.Name : null);

            return Protocol.Result(new JObject
            {
                ["mxd"] = mxdPath,
                ["titulo"] = app.Document.Title,
                ["data_frames"] = dataFrames,
                ["df_activo"] = doc.FocusMap != null ? doc.FocusMap.Name : null,
                ["escala_activa"] = escala,
                ["vista_activa"] = vistaActiva
            });
        }

        public static JObject ListLayers(JObject parameters)
        {
            IApplication app = ArcSession.App();
            IMxDocument doc = ArcSession.Doc(app);
            IMap map = doc.FocusMap;
            if (map == null)
                throw new InvalidOperationException("没有活动的数据框。");

            var capas = new JArray();
            // Recorrido recursivo (grupos incluidos), como arcpy ListLayers.
            IEnumLayer enumLayer = map.get_Layers(null, true);
            enumLayer.Reset();
            ILayer lyr;
            while ((lyr = enumLayer.Next()) != null)
            {
                var item = new JObject
                {
                    ["nombre"] = lyr.Name,
                    ["visible"] = lyr.Visible,
                    ["es_grupo"] = lyr is IGroupLayer
                };
                try
                {
                    IDataLayer2 dataLayer = lyr as IDataLayer2;
                    if (dataLayer != null && dataLayer.DataSourceName is IDatasetName dsn)
                    {
                        IWorkspaceName wsn = dsn.WorkspaceName;
                        item["fuente"] = wsn != null
                            ? System.IO.Path.Combine(wsn.PathName ?? "", dsn.Name)
                            : dsn.Name;
                    }
                }
                catch { /* capas sin fuente resoluble (rotas, servicios) */ }

                IFeatureLayerDefinition def = lyr as IFeatureLayerDefinition;
                if (def != null)
                    item["definition_query"] = def.DefinitionExpression ?? "";

                capas.Add(item);
            }

            return Protocol.Result(new JObject
            {
                ["data_frame"] = map.Name,
                ["num"] = capas.Count,
                ["capas"] = capas
            });
        }

        public static JObject ZoomToLayer(JObject parameters)
        {
            string nombre = (string)parameters["nombre"];
            if (string.IsNullOrEmpty(nombre))
                throw new ArgumentException("请提供 'nombre'（内容列表中的图层名称）。");

            IApplication app = ArcSession.App();
            IMxDocument doc = ArcSession.Doc(app);
            IMap map = doc.FocusMap;
            if (map == null)
                throw new InvalidOperationException("没有活动的数据框。");

            ILayer objetivo = null;
            IEnumLayer enumLayer = map.get_Layers(null, true);
            enumLayer.Reset();
            ILayer lyr;
            while ((lyr = enumLayer.Next()) != null)
            {
                if (string.Equals(lyr.Name, nombre, StringComparison.OrdinalIgnoreCase))
                {
                    objetivo = lyr;
                    break;
                }
            }
            if (objetivo == null)
                throw new ArgumentException("未找到图层：" + nombre);

            IEnvelope extent = objetivo.AreaOfInterest;
            if (extent == null || extent.IsEmpty)
                throw new InvalidOperationException("图层没有可用的范围：" + nombre);

            IActiveView mapView = (IActiveView)map;
            mapView.Extent = extent;
            doc.ActiveView.Refresh();

            return Protocol.Result(new JObject
            {
                ["capa"] = nombre,
                ["escala"] = map.MapScale
            });
        }
    }
}
