using System;
using System.Collections.Generic;
using ESRI.ArcGIS.ArcMapUI;
using ESRI.ArcGIS.Carto;
using ESRI.ArcGIS.Framework;
using Newtonsoft.Json.Linq;

namespace YghsBridge.AddIn.Handlers
{
    /// <summary>
    /// list_data_frames / set_active_df — contrato JSON que esperan los schemas
    /// del servidor MCP. Como el mxd.activeView de arcpy, activar un data frame
    /// conmuta a su vista de datos (IMxDocument.ActiveView tiene setter).
    /// </summary>
    internal static class DataFrameHandlers
    {
        public static JObject ListDataFrames(JObject parameters)
        {
            IApplication app = ArcSession.App();
            IMxDocument doc = ArcSession.Doc(app);
            IMaps maps = doc.Maps;
            string activo = doc.FocusMap != null ? doc.FocusMap.Name : null;

            var dataFrames = new JArray();
            for (int i = 0; i < maps.Count; i++)
            {
                IMap m = maps.get_Item(i);
                double? escala = null;
                try { escala = m.MapScale; } catch { /* escala no definida */ }
                dataFrames.Add(new JObject
                {
                    ["nombre"] = m.Name,
                    ["escala"] = escala,
                    ["activo"] = string.Equals(m.Name, activo, StringComparison.Ordinal)
                });
            }
            return Protocol.Result(new JObject
            {
                ["num"] = maps.Count,
                ["activo"] = activo,
                ["data_frames"] = dataFrames
            });
        }

        public static JObject SetActiveDf(JObject parameters)
        {
            string nombre = (string)parameters["nombre"];
            if (string.IsNullOrEmpty(nombre))
                throw new ArgumentException("请提供 'nombre'（要激活的数据框）。");

            IApplication app = ArcSession.App();
            IMxDocument doc = ArcSession.Doc(app);
            IMaps maps = doc.Maps;

            IMap objetivo = null;
            var disponibles = new List<string>();
            for (int i = 0; i < maps.Count; i++)
            {
                IMap m = maps.get_Item(i);
                disponibles.Add(m.Name);
                if (objetivo == null && string.Equals(m.Name, nombre, StringComparison.OrdinalIgnoreCase))
                    objetivo = m;
            }
            if (objetivo == null)
                throw new ArgumentException("未找到数据框：" + nombre
                    + "。可用数据框：" + string.Join(", ", disponibles));

            doc.ActiveView = (IActiveView)objetivo;
            doc.ActiveView.Refresh();
            return Protocol.Result(new JObject { ["activo"] = objetivo.Name });
        }
    }
}
