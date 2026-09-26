using System;
using System.Collections.Generic;
using ESRI.ArcGIS.ArcMapUI;
using ESRI.ArcGIS.Carto;
using ESRI.ArcGIS.Geodatabase;
using Newtonsoft.Json.Linq;

namespace YghsBridge.AddIn.Handlers
{
    /// <summary>
    /// select_by_attribute / clear_selection / get_unique_values / count_features /
    /// list_fields / get_layer_info / get_layer_features — contrato JSON que
    /// esperan los schemas del servidor MCP. Las consultas honran definition query y selección
    /// como arcpy.da.SearchCursor sobre una capa de la TOC: si hay selección se
    /// recorre el ISelectionSet; si no, la display table (joins + def. query).
    /// </summary>
    internal static class QueryHandlers
    {
        private static ILayer CapaRequerida(JObject parameters, IMap map)
        {
            string capa = (string)parameters["capa"];
            if (string.IsNullOrEmpty(capa))
                throw new ArgumentException("请提供 'capa'（内容列表中的名称）。");
            return MapHandlers.FindLayer(map, capa);
        }

        /// <summary>Cursor de lectura sobre la capa: selección si existe, display
        /// table si no. El where se combina con la definition query explícitamente
        /// para no depender de si SearchDisplayTable la aplica por su cuenta.</summary>
        private static ICursor CursorSobreCapa(ILayer lyr, string where, string subcampos)
        {
            IFeatureSelection fsel = lyr as IFeatureSelection;
            if (fsel != null && fsel.SelectionSet != null && fsel.SelectionSet.Count > 0)
            {
                IQueryFilter filtroSel = null;
                if (!string.IsNullOrEmpty(where) || !string.IsNullOrEmpty(subcampos))
                {
                    filtroSel = new QueryFilterClass();
                    if (!string.IsNullOrEmpty(where)) filtroSel.WhereClause = where;
                    if (!string.IsNullOrEmpty(subcampos)) filtroSel.SubFields = subcampos;
                }
                ICursor cursorSel;
                fsel.SelectionSet.Search(filtroSel, true, out cursorSel);
                return cursorSel;
            }

            IDisplayTable dt = lyr as IDisplayTable;
            if (dt == null)
                throw new ArgumentException("图层不支持属性查询：" + lyr.Name);

            IFeatureLayerDefinition def = lyr as IFeatureLayerDefinition;
            string combinado = DataAccess.CombinarWhere(
                def != null ? def.DefinitionExpression : null, where);
            IQueryFilter filtro = null;
            if (!string.IsNullOrEmpty(combinado) || !string.IsNullOrEmpty(subcampos))
            {
                filtro = new QueryFilterClass();
                if (!string.IsNullOrEmpty(combinado)) filtro.WhereClause = combinado;
                if (!string.IsNullOrEmpty(subcampos)) filtro.SubFields = subcampos;
            }
            return dt.SearchDisplayTable(filtro, true);
        }

        /// <summary>Campos de la capa con joins incluidos (display table), como
        /// arcpy.ListFields sobre la capa.</summary>
        private static IFields CamposDeCapa(ILayer lyr)
        {
            IDisplayTable dt = lyr as IDisplayTable;
            if (dt == null || dt.DisplayTable == null)
                throw new ArgumentException("图层没有可查询的属性表：" + lyr.Name);
            return dt.DisplayTable.Fields;
        }

        /// <summary>Conteo con la semántica del GetCount de arcpy: selección si la hay;
        /// si no, total honrando la definition query (RowCount es O(1) en gdb).</summary>
        private static int ContarFeatures(ILayer lyr, string where)
        {
            IFeatureSelection fsel = lyr as IFeatureSelection;
            bool haySeleccion = fsel != null && fsel.SelectionSet != null && fsel.SelectionSet.Count > 0;

            if (haySeleccion)
            {
                if (string.IsNullOrEmpty(where))
                    return fsel.SelectionSet.Count;
                int n = 0;
                ICursor cur = CursorSobreCapa(lyr, where, null);
                try
                {
                    while (cur.NextRow() != null)
                        n++;
                    return n;
                }
                finally
                {
                    if (cur != null) System.Runtime.InteropServices.Marshal.ReleaseComObject(cur);
                }
            }

            IDisplayTable dt = lyr as IDisplayTable;
            if (dt == null || dt.DisplayTable == null)
                throw new ArgumentException("图层不支持要素计数：" + lyr.Name);
            IFeatureLayerDefinition def = lyr as IFeatureLayerDefinition;
            string combinado = DataAccess.CombinarWhere(
                def != null ? def.DefinitionExpression : null, where);
            IQueryFilter filtro = null;
            if (!string.IsNullOrEmpty(combinado))
                filtro = new QueryFilterClass { WhereClause = combinado };
            return dt.DisplayTable.RowCount(filtro);
        }

        private static void RefrescarSeleccion(IMxDocument doc, IMap map)
        {
            IActiveView av = (IActiveView)map;
            av.PartialRefresh(esriViewDrawPhase.esriViewGeoSelection, null, null);
            doc.ActiveView.Refresh();
        }

        public static JObject SelectByAttribute(JObject parameters)
        {
            string where = (string)parameters["where"] ?? "";
            IMxDocument doc;
            IMap map = MapHandlers.FocusMap(out doc);
            ILayer lyr = CapaRequerida(parameters, map);
            IFeatureSelection fsel = lyr as IFeatureSelection;
            if (fsel == null)
                throw new ArgumentException("图层不支持按属性选择：" + lyr.Name);

            IQueryFilter filtro = new QueryFilterClass { WhereClause = where };
            fsel.SelectFeatures(filtro, esriSelectionResultEnum.esriSelectionResultNew, false);
            int n = fsel.SelectionSet != null ? fsel.SelectionSet.Count : 0;
            RefrescarSeleccion(doc, map);
            return Protocol.Result(new JObject
            {
                ["capa"] = lyr.Name,
                ["where"] = where,
                ["seleccionados"] = n
            });
        }

        public static JObject ClearSelection(JObject parameters)
        {
            string capa = (string)parameters["capa"];
            IMxDocument doc;
            IMap map = MapHandlers.FocusMap(out doc);

            var limpiadas = new JArray();
            if (!string.IsNullOrEmpty(capa))
            {
                ILayer lyr = MapHandlers.FindLayer(map, capa);
                IFeatureSelection fsel = lyr as IFeatureSelection;
                if (fsel == null)
                    throw new ArgumentException("图层不支持选择：" + capa);
                fsel.Clear();
                limpiadas.Add(lyr.Name);
            }
            else
            {
                IEnumLayer enumLayer = map.get_Layers(null, true);
                enumLayer.Reset();
                ILayer lyr;
                while ((lyr = enumLayer.Next()) != null)
                {
                    IFeatureSelection fsel = lyr as IFeatureSelection;
                    if (fsel == null)
                        continue;
                    try
                    {
                        fsel.Clear();
                        limpiadas.Add(lyr.Name);
                    }
                    catch { /* capas rotas o sin selección utilizable: seguir */ }
                }
            }
            RefrescarSeleccion(doc, map);
            return Protocol.Result(new JObject
            {
                ["capas"] = limpiadas,
                ["num"] = limpiadas.Count
            });
        }

        public static JObject GetUniqueValues(JObject parameters)
        {
            string campo = (string)parameters["campo"];
            if (string.IsNullOrEmpty(campo))
                throw new ArgumentException("请提供 'campo'。");
            string where = (string)parameters["where"];

            IMxDocument doc;
            IMap map = MapHandlers.FocusMap(out doc);
            ILayer lyr = CapaRequerida(parameters, map);

            ICursor cur = CursorSobreCapa(lyr, where, campo);
            int idx = cur.Fields.FindField(campo);
            if (idx < 0)
            {
                System.Runtime.InteropServices.Marshal.ReleaseComObject(cur);
                throw new ArgumentException("未找到字段：" + campo
                    + "。可用字段：" + NombresDeCampos(CamposDeCapa(lyr)));
            }

            var vistos = new HashSet<object>();
            IRow row;
            try
            {
                while ((row = cur.NextRow()) != null)
                {
                    object v = row.get_Value(idx);
                    vistos.Add(v is DBNull ? null : v);
                }
            }
            finally
            {
                System.Runtime.InteropServices.Marshal.ReleaseComObject(cur);
            }

            var lista = new List<object>(vistos);
            try
            {
                lista.Sort(Comparer<object>.Default);
            }
            catch { /* tipos mezclados no comparables: devolver sin ordenar */ }

            var valores = new JArray();
            foreach (object v in lista)
                valores.Add(DataAccess.ValorAJson(v));

            return Protocol.Result(new JObject
            {
                ["capa"] = lyr.Name,
                ["campo"] = campo,
                ["num"] = valores.Count,
                ["valores"] = valores
            });
        }

        public static JObject CountFeatures(JObject parameters)
        {
            string where = (string)parameters["where"];
            IMxDocument doc;
            IMap map = MapHandlers.FocusMap(out doc);
            ILayer lyr = CapaRequerida(parameters, map);
            int n = ContarFeatures(lyr, where);
            return Protocol.Result(new JObject
            {
                ["capa"] = lyr.Name,
                ["where"] = where,
                ["num"] = n
            });
        }

        public static JObject ListFields(JObject parameters)
        {
            IMxDocument doc;
            IMap map = MapHandlers.FocusMap(out doc);
            ILayer lyr = CapaRequerida(parameters, map);
            IFields fields = CamposDeCapa(lyr);

            var campos = new JArray();
            for (int i = 0; i < fields.FieldCount; i++)
            {
                IField f = fields.get_Field(i);
                campos.Add(new JObject
                {
                    ["nombre"] = f.Name,
                    ["tipo"] = DataAccess.NombreTipoCampo(f.Type),
                    ["alias"] = f.AliasName,
                    ["longitud"] = f.Length
                });
            }
            return Protocol.Result(new JObject
            {
                ["capa"] = lyr.Name,
                ["num"] = campos.Count,
                ["campos"] = campos
            });
        }

        public static JObject GetLayerInfo(JObject parameters)
        {
            IMxDocument doc;
            IMap map = MapHandlers.FocusMap(out doc);
            ILayer lyr = CapaRequerida(parameters, map);

            string tipoGeom = null;
            string crs = null;
            JObject ext = null;
            int? num = null;
            var campos = new JArray();

            IGeoDataset gds = null;
            IFeatureLayer fl = lyr as IFeatureLayer;
            if (fl != null)
            {
                try
                {
                    if (fl.FeatureClass != null)
                    {
                        tipoGeom = DataAccess.NombreTipoGeometria(fl.FeatureClass.ShapeType);
                        gds = fl.FeatureClass as IGeoDataset;
                    }
                }
                catch { /* fuente rota: seguir con lo que haya */ }
                try
                {
                    num = ContarFeatures(lyr, null);
                }
                catch { }
                try
                {
                    IFields fields = CamposDeCapa(lyr);
                    for (int i = 0; i < fields.FieldCount; i++)
                    {
                        IField f = fields.get_Field(i);
                        campos.Add(new JObject
                        {
                            ["nombre"] = f.Name,
                            ["tipo"] = DataAccess.NombreTipoCampo(f.Type)
                        });
                    }
                }
                catch { }
            }
            else
            {
                // Capas no vectoriales (ráster, TIN...): CRS y extent del propio dataset.
                gds = lyr as IGeoDataset;
            }

            if (gds != null)
            {
                try
                {
                    if (gds.SpatialReference != null)
                        crs = gds.SpatialReference.Name;
                }
                catch { }
                try
                {
                    ESRI.ArcGIS.Geometry.IEnvelope e = gds.Extent;
                    if (e != null && !e.IsEmpty)
                        ext = new JObject
                        {
                            ["xmin"] = e.XMin,
                            ["ymin"] = e.YMin,
                            ["xmax"] = e.XMax,
                            ["ymax"] = e.YMax
                        };
                }
                catch { }
            }

            string workspace;
            string fuente = DataAccess.RutaFuente(lyr, out workspace);

            return Protocol.Result(new JObject
            {
                ["capa"] = lyr.Name,
                ["tipo_geometria"] = tipoGeom,
                ["crs"] = crs,
                ["extent"] = ext,
                ["num_features"] = num,
                ["campos"] = campos,
                ["fuente"] = fuente
            });
        }

        public static JObject GetLayerFeatures(JObject parameters)
        {
            string where = (string)parameters["where"];
            JArray camposParam = parameters["campos"] as JArray;
            int limite = parameters["limite"] != null && parameters["limite"].Type != JTokenType.Null
                ? (int)parameters["limite"] : 50;

            IMxDocument doc;
            IMap map = MapHandlers.FocusMap(out doc);
            ILayer lyr = CapaRequerida(parameters, map);

            var nombres = new List<string>();
            string subcampos = null;
            if (camposParam != null && camposParam.Count > 0)
            {
                foreach (JToken t in camposParam)
                    nombres.Add((string)t);
                subcampos = string.Join(",", nombres);
            }
            else
            {
                // Todos salvo geometría/blob/ráster.
                IFields fields = CamposDeCapa(lyr);
                for (int i = 0; i < fields.FieldCount; i++)
                {
                    IField f = fields.get_Field(i);
                    if (f.Type == esriFieldType.esriFieldTypeGeometry
                        || f.Type == esriFieldType.esriFieldTypeBlob
                        || f.Type == esriFieldType.esriFieldTypeRaster)
                        continue;
                    nombres.Add(f.Name);
                }
            }

            ICursor cur = CursorSobreCapa(lyr, where, subcampos);
            var indices = new int[nombres.Count];
            for (int i = 0; i < nombres.Count; i++)
            {
                indices[i] = cur.Fields.FindField(nombres[i]);
                if (indices[i] < 0)
                {
                    System.Runtime.InteropServices.Marshal.ReleaseComObject(cur);
                    throw new ArgumentException("未找到字段：" + nombres[i]
                        + "。可用字段：" + NombresDeCampos(CamposDeCapa(lyr)));
                }
            }

            var filas = new JArray();
            IRow row;
            try
            {
                while (filas.Count < limite && (row = cur.NextRow()) != null)
                {
                    var fila = new JObject();
                    for (int i = 0; i < nombres.Count; i++)
                        fila[nombres[i]] = DataAccess.ValorAJson(row.get_Value(indices[i]));
                    filas.Add(fila);
                }
            }
            finally
            {
                System.Runtime.InteropServices.Marshal.ReleaseComObject(cur);
            }

            return Protocol.Result(new JObject
            {
                ["capa"] = lyr.Name,
                ["campos"] = new JArray(nombres),
                ["num"] = filas.Count,
                ["limite"] = limite,
                ["filas"] = filas
            });
        }

        private static string NombresDeCampos(IFields fields)
        {
            var nombres = new List<string>();
            for (int i = 0; i < fields.FieldCount; i++)
                nombres.Add(fields.get_Field(i).Name);
            return string.Join(", ", nombres);
        }
    }
}
