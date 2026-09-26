using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using ESRI.ArcGIS.ArcMapUI;
using ESRI.ArcGIS.Carto;
using ESRI.ArcGIS.Display;
using ESRI.ArcGIS.Geodatabase;
using ESRI.ArcGIS.Geometry;
using Newtonsoft.Json.Linq;

namespace YghsBridge.AddIn.Handlers
{
    /// <summary>
    /// Simbología CATEGÓRICA por valores únicos, complemento de la graduada.
    ///
    /// Antes de esto la única vía era preparar un .lyr plantilla a mano y
    /// aplicarlo con apply_symbology_from_layer, o sea salir de la sesión para
    /// cada leyenda nueva.
    /// </summary>
    internal static class UniqueValuesHandlers
    {
        /// <summary>Tope de categorías. Una leyenda de miles de entradas no es una
        /// leyenda: es un cuelgue. Mejor fallar diciendo el número real.</summary>
        private const int MaxCategorias = 100;

        public static JObject SetUniqueValuesSymbology(JObject parameters)
        {
            string capa = (string)parameters["capa"];
            string campo = (string)parameters["campo"];
            if (string.IsNullOrEmpty(capa) || string.IsNullOrEmpty(campo))
                throw new ArgumentException("请提供 'capa'（内容列表中的名称）和 'campo'（用于分类的字段）。");

            IMxDocument doc;
            IMap map = MapHandlers.FocusMap(out doc);
            ILayer encontrada = MapHandlers.FindLayer(map, capa);
            IGeoFeatureLayer gfl = encontrada as IGeoFeatureLayer;
            if (gfl == null)
            {
                string queEs = encontrada == null
                    ? "内容列表中没有该名称的图层"
                    : (encontrada is IRasterLayer
                        ? "是栅格图层；请改用 set_raster_symbology"
                        : "不是要素图层");
                throw new ArgumentException("'" + capa + "': " + queEs + ".");
            }

            IFeatureClass fc = gfl.FeatureClass;
            if (fc == null)
                throw new ArgumentException("图层没有可访问的数据源（是否损坏？）：" + capa);

            int idx = fc.FindField(campo);
            if (idx < 0)
                throw new ArgumentException("在图层中未找到字段 '" + capa + "': " + campo);

            List<string> valores = ValoresUnicos(fc, campo);
            if (valores.Count == 0)
                throw new ArgumentException("字段 '" + campo + "' 没有任何值：无法分类。");
            if (valores.Count > MaxCategorias)
                throw new ArgumentException("字段 '" + campo + "' 有 " + valores.Count
                    + " 个不同的值，超过上限 " + MaxCategorias
                    + "。这样的图例不可读：请先对字段分组，或使用 "
                    + "set_graduated_symbology（若字段为连续数值型）。");

            esriGeometryType shp = fc.ShapeType;
            double tam = LeerDouble(parameters["tamano"],
                shp == esriGeometryType.esriGeometryPolyline ? 2.0
                : shp == esriGeometryType.esriGeometryPolygon ? 0.4 : 6.0);

            IColor[] paleta = Paleta(parameters, valores.Count);

            IUniqueValueRenderer render = new UniqueValueRendererClass();
            render.FieldCount = 1;
            render.set_Field(0, campo);
            // Sin símbolo por defecto: si aparece un valor nuevo que no está en la
            // leyenda, es mejor que NO se dibuje a que se cuele con un color
            // cualquiera y parezca una categoría más.
            render.UseDefaultSymbol = false;

            for (int i = 0; i < valores.Count; i++)
            {
                ISymbol simbolo = Simbolo(shp, paleta[i], tam);
                render.AddValue(valores[i], campo, simbolo);
                render.set_Label(valores[i], valores[i]);
            }

            gfl.Renderer = (IFeatureRenderer)render;
            MapHandlers.NotificarCambioContenido(map, doc);

            var lista = new JArray();
            foreach (string v in valores)
                lista.Add(v);

            return Protocol.Result(new JObject
            {
                ["capa"] = gfl.Name,
                ["campo"] = campo,
                ["num_categorias"] = valores.Count,
                ["valores"] = lista,
            });
        }

        /// <summary>Valores distintos del campo, vía IDataStatistics.</summary>
        private static List<string> ValoresUnicos(IFeatureClass fc, string campo)
        {
            var salida = new List<string>();
            ICursor cursor = (ICursor)fc.Search(null, false);
            try
            {
                IDataStatistics stats = new DataStatisticsClass
                {
                    Field = campo,
                    Cursor = cursor
                };
                IEnumerator e = stats.UniqueValues;
                e.Reset();
                while (e.MoveNext())
                {
                    object v = e.Current;
                    // NULL se salta a propósito: AddValue con null revienta, y una
                    // categoría "nada" no aporta.
                    if (v == null || v == DBNull.Value)
                        continue;
                    salida.Add(Convert.ToString(v, CultureInfo.InvariantCulture));
                }
            }
            finally
            {
                // Los cursores de ArcObjects hay que soltarlos o dejan lock sobre la
                // fuente; con shapefiles en red eso se nota enseguida.
                if (cursor != null)
                    System.Runtime.InteropServices.Marshal.ReleaseComObject(cursor);
            }
            salida.Sort(StringComparer.OrdinalIgnoreCase);
            return salida;
        }

        /// <summary>
        /// Paleta para categorías. Por defecto tonos bien separados en el círculo
        /// cromático: en categórico lo que importa es DISTINGUIR, no ordenar, así
        /// que una rampa secuencial (la de la graduada) sería justo lo contrario.
        /// Si se pasan color_desde y color_hasta se respeta esa rampa.
        /// </summary>
        private static IColor[] Paleta(JObject parameters, int n)
        {
            var salida = new IColor[n];
            bool rampaExplicita = parameters["color_desde"] != null || parameters["color_hasta"] != null;

            if (rampaExplicita)
            {
                IColor desde = LeerColor(parameters["color_desde"], 255, 255, 178);
                IColor hasta = LeerColor(parameters["color_hasta"], 189, 0, 38);
                IAlgorithmicColorRamp rampa = new AlgorithmicColorRampClass
                {
                    Algorithm = esriColorRampAlgorithm.esriHSVAlgorithm,
                    FromColor = desde,
                    ToColor = hasta,
                    Size = n
                };
                bool ok;
                rampa.CreateRamp(out ok);
                if (ok)
                {
                    IEnumColors colores = rampa.Colors;
                    colores.Reset();
                    for (int i = 0; i < n; i++)
                        salida[i] = colores.Next() ?? hasta;
                    return salida;
                }
            }

            // Tonos repartidos por el círculo, saturación y valor fijos. Reproducible
            // a propósito: la misma capa con el mismo campo sale siempre igual, que
            // es lo que se espera al reexportar una serie de planos.
            for (int i = 0; i < n; i++)
            {
                double hue = (360.0 * i) / n;
                salida[i] = DesdeHsv(hue, 0.65, 0.90);
            }
            return salida;
        }

        private static IColor DesdeHsv(double h, double s, double v)
        {
            double c = v * s;
            double x = c * (1 - Math.Abs(((h / 60.0) % 2) - 1));
            double m = v - c;
            double r1, g1, b1;
            if (h < 60) { r1 = c; g1 = x; b1 = 0; }
            else if (h < 120) { r1 = x; g1 = c; b1 = 0; }
            else if (h < 180) { r1 = 0; g1 = c; b1 = x; }
            else if (h < 240) { r1 = 0; g1 = x; b1 = c; }
            else if (h < 300) { r1 = x; g1 = 0; b1 = c; }
            else { r1 = c; g1 = 0; b1 = x; }
            return new RgbColorClass
            {
                Red = (int)Math.Round((r1 + m) * 255),
                Green = (int)Math.Round((g1 + m) * 255),
                Blue = (int)Math.Round((b1 + m) * 255)
            };
        }

        private static ISymbol Simbolo(esriGeometryType shp, IColor color, double tam)
        {
            switch (shp)
            {
                case esriGeometryType.esriGeometryPolygon:
                    ISimpleLineSymbol borde = new SimpleLineSymbolClass
                    {
                        Color = new RgbColorClass { Red = 110, Green = 110, Blue = 110 },
                        Width = tam
                    };
                    ISimpleFillSymbol relleno = new SimpleFillSymbolClass
                    {
                        Color = color,
                        Style = esriSimpleFillStyle.esriSFSSolid,
                        Outline = borde
                    };
                    return (ISymbol)relleno;

                case esriGeometryType.esriGeometryPolyline:
                    ISimpleLineSymbol linea = new SimpleLineSymbolClass
                    {
                        Color = color,
                        Width = tam,
                        Style = esriSimpleLineStyle.esriSLSSolid
                    };
                    return (ISymbol)linea;

                default:
                    ISimpleMarkerSymbol punto = new SimpleMarkerSymbolClass
                    {
                        Color = color,
                        Size = tam,
                        Style = esriSimpleMarkerStyle.esriSMSCircle
                    };
                    return (ISymbol)punto;
            }
        }

        private static IColor LeerColor(JToken t, int rDef, int gDef, int bDef)
        {
            int r = rDef, g = gDef, b = bDef;
            JArray arr = t as JArray;
            if (arr != null && arr.Count >= 3)
            {
                r = (int)arr[0];
                g = (int)arr[1];
                b = (int)arr[2];
            }
            if (r < 0 || r > 255 || g < 0 || g > 255 || b < 0 || b > 255)
                throw new ArgumentException("颜色格式为 [R, G, B]，取值 0-255。");
            return new RgbColorClass { Red = r, Green = g, Blue = b };
        }

        private static double LeerDouble(JToken t, double porDefecto)
        {
            return t == null || t.Type == JTokenType.Null ? porDefecto : (double)t;
        }
    }
}
