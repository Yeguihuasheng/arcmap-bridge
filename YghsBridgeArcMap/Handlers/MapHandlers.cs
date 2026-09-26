using System;
using System.Collections.Generic;
using ESRI.ArcGIS.ArcMapUI;
using ESRI.ArcGIS.Carto;
using ESRI.ArcGIS.Framework;
using ESRI.ArcGIS.Geodatabase;
using ESRI.ArcGIS.Geometry;
using Newtonsoft.Json.Linq;

namespace YghsBridge.AddIn.Handlers
{
    /// <summary>
    /// set_scale / set_extent / set_layer_visibility / set_definition_query —
    /// contrato JSON que esperan los schemas del servidor MCP. La búsqueda de
    /// capa devuelve un error accionable con la lista de capas disponibles si
    /// el nombre no existe.
    /// </summary>
    internal static class MapHandlers
    {
        internal static ILayer FindLayer(IMap map, string nombre)
        {
            ILayer objetivo = null;
            var disponibles = new List<string>();
            IEnumLayer enumLayer = map.get_Layers(null, true);
            enumLayer.Reset();
            ILayer lyr;
            while ((lyr = enumLayer.Next()) != null)
            {
                disponibles.Add(lyr.Name);
                if (objetivo == null && string.Equals(lyr.Name, nombre, StringComparison.OrdinalIgnoreCase))
                    objetivo = lyr;
            }
            if (objetivo == null)
                throw new ArgumentException("未找到图层：" + nombre
                    + "。可用图层：" + string.Join(", ", disponibles));
            return objetivo;
        }

        internal static IMap FocusMap(out IMxDocument doc)
        {
            IApplication app = ArcSession.App();
            doc = ArcSession.Doc(app);
            IMap map = doc.FocusMap;
            if (map == null)
                throw new InvalidOperationException("没有活动的数据框。");
            return map;
        }

        /// <summary>Tras mutar el CONTENIDO del mapa (visibilidad, def. query, alta/
        /// baja de capa, simbología) hay que llamar a IActiveView.ContentsChanged()
        /// del MAPA: es el aviso que escuchan los map surrounds. Sin él, una leyenda
        /// con "only display checked layers" se queda con el estado viejo en los
        /// exports (el clic manual en la TOC dispara el evento; el setter
        /// programático, no).</summary>
        internal static void NotificarCambioContenido(IMap map, IMxDocument doc)
        {
            ((IActiveView)map).ContentsChanged();
            doc.UpdateContents();
            doc.ActiveView.Refresh();
        }

        /// <summary>refresh — redibuja la vista activa y la TOC (equivalente a
        /// RefreshActiveView + RefreshTOC de arcpy).</summary>
        public static JObject Refresh(JObject parameters)
        {
            IMxDocument doc;
            FocusMap(out doc);
            doc.UpdateContents();
            doc.ActiveView.Refresh();
            return Protocol.Result(new JObject { ["refrescado"] = true });
        }

        public static JObject SetScale(JObject parameters)
        {
            if (parameters["escala"] == null || parameters["escala"].Type == JTokenType.Null)
                throw new ArgumentException("请提供 'escala'（如 200000 = 1:200000）。");
            double escala = (double)parameters["escala"];

            IMxDocument doc;
            IMap map = FocusMap(out doc);
            map.MapScale = escala;
            doc.ActiveView.Refresh();
            return Protocol.Result(new JObject { ["escala"] = map.MapScale });
        }

        public static JObject SetExtent(JObject parameters)
        {
            JArray coords = parameters["coords"] as JArray;
            string capa = (string)parameters["capa"];

            IMxDocument doc;
            IMap map = FocusMap(out doc);

            IEnvelope ext;
            if (coords != null)
            {
                if (coords.Count != 4)
                    throw new ArgumentException("'coords' 必须为 [xmin, ymin, xmax, ymax]。");
                ext = new EnvelopeClass();
                ext.PutCoords((double)coords[0], (double)coords[1],
                              (double)coords[2], (double)coords[3]);
            }
            else if (!string.IsNullOrEmpty(capa))
            {
                ILayer lyr = FindLayer(map, capa);
                ext = ExtentSeleccion(lyr) ?? lyr.AreaOfInterest;
                if (ext == null || ext.IsEmpty)
                    throw new InvalidOperationException("图层没有可用的范围：" + capa);
            }
            else
            {
                throw new ArgumentException("请提供 'coords' [xmin,ymin,xmax,ymax] 或 'capa'。");
            }

            IActiveView mapView = (IActiveView)map;
            mapView.Extent = ext;
            doc.ActiveView.Refresh();

            IEnvelope e = mapView.Extent;
            return Protocol.Result(new JObject
            {
                ["extent"] = new JObject
                {
                    ["xmin"] = e.XMin,
                    ["ymin"] = e.YMin,
                    ["xmax"] = e.XMax,
                    ["ymax"] = e.YMax
                },
                ["escala"] = map.MapScale
            });
        }

        /// <summary>Extent de la selección de la capa (unión de los envelopes de las
        /// features seleccionadas), o null si no hay selección — equivalente al
        /// lyr.getSelectedExtent(False) de arcpy.mapping.</summary>
        private static IEnvelope ExtentSeleccion(ILayer lyr)
        {
            try
            {
                IFeatureSelection fsel = lyr as IFeatureSelection;
                if (fsel == null || fsel.SelectionSet == null || fsel.SelectionSet.Count == 0)
                    return null;
                ICursor cursor;
                fsel.SelectionSet.Search(null, true, out cursor);
                try
                {
                    IFeatureCursor featureCursor = (IFeatureCursor)cursor;
                    IEnvelope acumulado = new EnvelopeClass();
                    acumulado.SetEmpty();
                    IFeature feature;
                    while ((feature = featureCursor.NextFeature()) != null)
                    {
                        if (feature.Shape != null && !feature.Shape.IsEmpty)
                            acumulado.Union(feature.Shape.Envelope);
                    }
                    return acumulado.IsEmpty ? null : acumulado;
                }
                finally
                {
                    if (cursor != null) System.Runtime.InteropServices.Marshal.ReleaseComObject(cursor);
                }
            }
            catch
            {
                return null; // sin selección utilizable: caer al extent total
            }
        }

        public static JObject SetLayerVisibility(JObject parameters)
        {
            string capa = (string)parameters["capa"];
            if (string.IsNullOrEmpty(capa))
                throw new ArgumentException("请提供 'capa'（内容列表中的名称）。");
            bool visible = parameters["visible"] == null || parameters["visible"].Type == JTokenType.Null
                ? true : (bool)parameters["visible"];

            IMxDocument doc;
            IMap map = FocusMap(out doc);
            ILayer lyr = FindLayer(map, capa);
            lyr.Visible = visible;
            NotificarCambioContenido(map, doc);
            return Protocol.Result(new JObject { ["capa"] = capa, ["visible"] = visible });
        }

        public static JObject SetDefinitionQuery(JObject parameters)
        {
            string capa = (string)parameters["capa"];
            if (string.IsNullOrEmpty(capa))
                throw new ArgumentException("请提供 'capa'（内容列表中的名称）。");
            string query = (string)parameters["query"];

            IMxDocument doc;
            IMap map = FocusMap(out doc);
            ILayer lyr = FindLayer(map, capa);
            IFeatureLayerDefinition def = lyr as IFeatureLayerDefinition;
            if (def == null)
                throw new ArgumentException("图层不支持定义查询：" + capa);

            string anterior = def.DefinitionExpression ?? "";
            def.DefinitionExpression = string.IsNullOrEmpty(query) ? "" : query;
            NotificarCambioContenido(map, doc);
            return Protocol.Result(new JObject
            {
                ["capa"] = capa,
                ["query_anterior"] = anterior,
                ["query_nueva"] = def.DefinitionExpression ?? ""
            });
        }
    }
}
