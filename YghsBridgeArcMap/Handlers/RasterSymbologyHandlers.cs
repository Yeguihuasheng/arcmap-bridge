using System;
using System.Globalization;
using ESRI.ArcGIS.ArcMapUI;
using ESRI.ArcGIS.Carto;
using ESRI.ArcGIS.DataSourcesRaster;
using ESRI.ArcGIS.Display;
using ESRI.ArcGIS.Geodatabase;
using Newtonsoft.Json.Linq;

namespace YghsBridge.AddIn.Handlers
{
    /// <summary>
    /// Simbología de RÁSTER: clasificada y estirada.
    ///
    /// Por qué existe este fichero aparte: `set_graduated_symbology` exige un
    /// IGeoFeatureLayer (LayerHandlers.cs), así que hasta 2026-08-27 NO había
    /// forma de simbolizar un ráster desde el MCP. `execute_arcpy` tampoco valía:
    /// opera sobre una copia del documento y los cambios al renderer se descartan
    /// por diseño (ADR-004). Era el hueco más pegado a los flujos reales de IDEN,
    /// donde casi todo el producto es ráster: NDVI, FCC, P95, pendientes.
    ///
    /// La familia de interfaces es OTRA que en vectorial: aquí manda
    /// IRasterRenderer (+ IRasterClassifyColorRampRenderer o
    /// IRasterStretchColorRampRenderer), no IFeatureRenderer, y el orden de las
    /// llamadas importa — ver el comentario de Update() más abajo.
    /// </summary>
    internal static class RasterSymbologyHandlers
    {
        /// <summary>
        /// set_raster_symbology: aplica simbología a una capa ráster de la TOC.
        ///
        /// modo="clasificado" (por defecto): N clases con rampa de color.
        /// modo="estirado": rampa continua entre el mínimo y el máximo.
        /// </summary>
        public static JObject SetRasterSymbology(JObject parameters)
        {
            string capa = (string)parameters["capa"];
            if (string.IsNullOrEmpty(capa))
                throw new ArgumentException("请提供 'capa'（内容列表中的栅格名称）。");

            string modo = ((string)parameters["modo"] ?? "clasificado").ToLowerInvariant();
            if (modo == "classified") modo = "clasificado";
            if (modo == "stretched") modo = "estirado";
            if (modo == "unique" || modo == "unique_values" || modo == "unicos") modo = "unico";
            if (modo != "clasificado" && modo != "estirado" && modo != "unico")
                throw new ArgumentException("'modo' 必须为 'clasificado'、'estirado' 或 'unico' "
                    + "（别名：classified / stretched / unique）。收到值：" + modo);

            IMxDocument doc;
            IMap map = MapHandlers.FocusMap(out doc);
            ILayer capaEncontrada = MapHandlers.FindLayer(map, capa);
            IRasterLayer rl = capaEncontrada as IRasterLayer;
            if (rl == null)
            {
                // Mensaje que REDIRIGE en vez de solo negar: el error mudo es lo que
                // costó una sesión entera de trabajo real.
                string queEs = capaEncontrada == null
                    ? "内容列表中没有该名称的图层"
                    : (capaEncontrada is IGeoFeatureLayer
                        ? "是要素图层；请改用 set_graduated_symbology"
                          + "（分级）或 set_unique_values_symbology（唯一值）"
                        : "不是栅格图层");
                throw new ArgumentException("'" + capa + "': " + queEs + ".");
            }

            IRaster raster = rl.Raster;
            if (raster == null)
                throw new ArgumentException("栅格图层 '" + capa
                    + "' 的数据不可访问（数据源是否损坏？）。请用 list_broken_data_sources 检查。");

            IColor desde = LeerColor(parameters["color_desde"], 255, 255, 178);
            IColor hasta = LeerColor(parameters["color_hasta"], 189, 0, 38);

            JObject detalle;
            if (modo == "clasificado")
                detalle = AplicarClasificado(rl, raster, parameters, desde, hasta);
            else if (modo == "unico")
                detalle = AplicarValoresUnicos(rl, raster, parameters);
            else
                detalle = AplicarEstirado(rl, raster, desde, hasta, LeerAlgoritmo(parameters["algoritmo"]));

            // La opacidad de un ráster temático no es decoración: es lo que deja
            // ver la ortofoto debajo, y en QGIS viaja con el estilo. Aquí es un
            // parámetro de cualquier modo, no solo del de valores únicos.
            JToken transp = parameters["transparencia"];
            if (transp != null && transp.Type != JTokenType.Null)
            {
                int pct = LeerInt(transp, 0);
                if (pct < 0 || pct > 100)
                    throw new ArgumentException("'transparencia' 必须在 0 到 100 之间（百分比）。收到值：" + pct);
                ILayerEffects efectos = rl as ILayerEffects;
                if (efectos == null || !efectos.SupportsTransparency)
                    throw new ArgumentException("图层 '" + capa + "' 不支持透明度。");
                efectos.Transparency = (short)pct;
                detalle["transparencia"] = pct;
            }

            MapHandlers.NotificarCambioContenido(map, doc);

            detalle["capa"] = rl.Name;
            detalle["modo"] = modo;
            return Protocol.Result(detalle);
        }

        private static JObject AplicarClasificado(IRasterLayer rl, IRaster raster,
            JObject parameters, IColor desde, IColor hasta)
        {
            int numClases = LeerInt(parameters["num_clases"], 5);
            if (numClases < 2 || numClases > 32)
                throw new ArgumentException("'num_clases' 必须在 2 到 32 之间。");

            // Sin estadísticas no hay clasificación posible: el renderer necesita
            // saber mínimo, máximo e histograma. Muchos .tif llegan sin ellas (los
            // que salen de un geoproceso, típicamente), y el síntoma es un E_FAIL
            // mudo desde COM. Se calculan aquí en vez de mandar al usuario a
            // hacerlo a mano, que es lo que hacía la primera versión de esto.
            AsegurarEstadisticas(raster);

            IRasterClassifyColorRampRenderer clasificado = new RasterClassifyColorRampRendererClass();
            IRasterRenderer render = (IRasterRenderer)clasificado;

            // ORDEN OBLIGATORIO, y es la trampa de esta API: Raster → Update() →
            // ClassCount → Update(). El PRIMER Update() es el que hace que el
            // renderer lea el ráster y construya una clasificación por defecto; si
            // se pone ClassCount antes de eso, no hay nada sobre lo que reclasificar
            // y Update() revienta con E_FAIL.
            render.Raster = raster;
            try
            {
                render.Update();
                clasificado.ClassCount = numClases;
                render.Update();
            }
            catch (Exception ex)
            {
                throw new ArgumentException("无法将栅格分为 " + numClases
                    + " 个类别：" + ex.Message
                    + "。请确认该波段取值多样且统计量有效；"
                    + "恒值栅格或全为 NoData 的栅格无法分类。");
            }

            int nReal = clasificado.ClassCount;

            // Los colores salen de una de dos vías, y la explícita manda: o los N
            // colores que da quien llama, o una rampa entre los dos extremos. Los
            // explícitos son la ÚNICA vía fiable cuando las clases son categóricas
            // o los cortes vienen fijados por percentil, porque entonces el color
            // no es un gradiente que se pueda derivar: es una decisión por clase.
            IColor[] paleta = LeerPaleta(parameters["colores"], nReal);
            if (paleta == null)
                paleta = ConstruirRampa(desde, hasta, nReal, LeerAlgoritmo(parameters["algoritmo"]));

            string[] etiquetas = LeerEtiquetas(parameters["etiquetas"], nReal);

            var cortes = new JArray();
            for (int i = 0; i < nReal; i++)
            {
                ISimpleFillSymbol relleno = new SimpleFillSymbolClass
                {
                    Color = paleta[i],
                    Style = esriSimpleFillStyle.esriSFSSolid
                };
                // Sin borde: en un ráster el contorno de cada clase es ruido visual.
                ISimpleLineSymbol sinBorde = new SimpleLineSymbolClass
                {
                    Style = esriSimpleLineStyle.esriSLSNull
                };
                relleno.Outline = sinBorde;

                clasificado.set_Symbol(i, (ISymbol)relleno);

                // OJO con la indexación de get_Break, que costó un diagnóstico:
                // el array tiene ClassCount+1 valores y el 0 es el MÍNIMO del
                // ráster, no el techo de la primera clase. El techo de la clase i
                // es get_Break(i+1). Leer 0..n-1 (lo que hacía esto hasta el
                // 2026-09-04) usaba el mínimo como techo de la clase 0 y nunca
                // llegaba a leer el techo de la última: sobre un ráster de enteros
                // 1..5 con 5 clases devolvía [1,1,2,3,4] en vez de [1,2,3,4,5], y
                // la leyenda salía rotulada con el corte duplicado.
                double inf = clasificado.get_Break(i);
                double sup = clasificado.get_Break(i + 1);
                clasificado.set_Label(i, etiquetas != null
                    ? etiquetas[i]
                    : Etiqueta(inf) + " – " + Etiqueta(sup));
                cortes.Add(sup);
            }

            // Segundo Update(): consolida símbolos y etiquetas en la leyenda.
            render.Update();
            rl.Renderer = render;

            return new JObject
            {
                ["num_clases"] = nReal,
                ["cortes"] = cortes,
            };
        }

        /// <summary>
        /// Valores únicos: un color por valor de píxel. Es lo que pide un ráster
        /// CATEGÓRICO —una máscara de visibilidad, un FCC binario, cualquier
        /// reclasificación, un `paletted` traído de QGIS—, y hasta 2026-09-11 no
        /// tenía camino: el modo clasificado revienta con un E_FAIL de COM sobre
        /// valores 0/1/2 porque no hay histograma que cortar, y clasificar una
        /// categoría sería mentir sobre el dato de todas formas.
        ///
        /// `transparentes` es la pieza que no se ve venir: en QGIS el paletted
        /// deja SIN PINTAR todo valor que no esté en la paleta, y ahí es donde va
        /// 0 表示"不可见"，通常占栅格的 90%。其精确对应是一个颜色设为
        /// NullColor 的类：它不绘制任何内容，ArcMap 也不会把它放进图例。
        /// 没有它，栅格会盖住整张地图。
        /// </summary>
        private static JObject AplicarValoresUnicos(IRasterLayer rl, IRaster raster, JObject parameters)
        {
            double[] valores = LeerValores(parameters["valores"], "valores");
            if (valores == null || valores.Length == 0)
                throw new ArgumentException("在 'unico' 模式下需要 'valores'：要绘制的像素值列表"
                    + "（如 [1, 2]）。无法从栅格自动推断：较大的栅格不会"
                    + "为此附带属性表，硬猜就等于编造图例。");
            if (valores.Length > 100)
                throw new ArgumentException("'valores' 含 " + valores.Length
                    + " 个条目；上限为 100。超过这个数就不是图例而是色表了："
                    + "请改用 'clasificado' 模式，或用 apply_symbology_from_layer 加载一个 .lyr。");

            double[] transparentes = LeerValores(parameters["transparentes"], "transparentes") ?? new double[0];
            IColor[] paleta = LeerPaleta(parameters["colores"], valores.Length)
                ?? PaletaCategorica(valores.Length);
            string[] etiquetas = LeerEtiquetas(parameters["etiquetas"], valores.Length);

            IRasterUniqueValueRenderer uvr = new RasterUniqueValueRendererClass();
            IRasterRenderer render = (IRasterRenderer)uvr;
            render.Raster = raster;

            int total = valores.Length + transparentes.Length;
            uvr.Field = "Value";
            uvr.HeadingCount = 1;
            uvr.set_Heading(0, "Value");
            uvr.set_ClassCount(0, total);

            int clase = 0;
            var pintados = new JArray();
            for (int i = 0; i < valores.Length; i++, clase++)
            {
                uvr.AddValue(0, clase, ValorDePixel(valores[i]));
                uvr.set_Symbol(0, clase, SimboloPlano(paleta[i]));
                uvr.set_Label(0, clase, etiquetas != null ? etiquetas[i] : Etiqueta(valores[i]));
                pintados.Add(valores[i]);
            }
            foreach (double v in transparentes)
            {
                IColor nulo = new RgbColorClass { Red = 255, Green = 255, Blue = 255, NullColor = true };
                uvr.AddValue(0, clase, ValorDePixel(v));
                uvr.set_Symbol(0, clase, SimboloPlano(nulo));
                uvr.set_Label(0, clase, "");   // vacía: ArcMap no la saca en la leyenda
                clase++;
            }

            try
            {
                render.Update();
            }
            catch (Exception ex)
            {
                throw new ArgumentException("无法应用唯一值符号系统："
                    + ex.Message + "。请确认这些值在栅格中存在且类型为 "
                    + "正确的像素类型（整型栅格与小数取值不匹配）。");
            }
            rl.Renderer = render;

            return new JObject
            {
                ["valores"] = pintados,
                ["transparentes"] = new JArray(transparentes),
                // La cabecera de la leyenda no se puede elegir: Update() la deja en
                // el nombre crudo del campo y después es de solo lectura
                // (E_INVALIDARG). Se quita en el elemento de leyenda del layout.
                ["cabecera_leyenda"] = "Value"
            };
        }

        private static object ValorDePixel(double v)
        {
            // Un ráster de enteros no casa con un valor decimal: AddValue acepta el
            // object tal cual y luego el Update() no encuentra la clase. Si el valor
            // es entero se manda como entero.
            if (Math.Abs(v - Math.Round(v)) < 1e-9 && Math.Abs(v) < int.MaxValue)
                return (int)Math.Round(v);
            return v;
        }

        private static ISymbol SimboloPlano(IColor color)
        {
            ISimpleFillSymbol relleno = new SimpleFillSymbolClass
            {
                Color = color,
                Style = esriSimpleFillStyle.esriSFSSolid
            };
            // Sin borde: en un ráster el contorno de cada clase es ruido visual.
            ISimpleLineSymbol sinBorde = new SimpleLineSymbolClass
            {
                Style = esriSimpleLineStyle.esriSLSNull
            };
            relleno.Outline = sinBorde;
            return (ISymbol)relleno;
        }

        /// <summary>
        /// Paleta por defecto para categorías: tonos repartidos por el círculo
        /// cromático. Misma decisión que en `set_unique_values_symbology`: en
        /// categórico hay que DISTINGUIR, no ordenar, y una rampa secuencial es
        /// justo lo contrario. Reproducible a propósito (mismos N = mismos colores),
        /// que importa al reexportar una serie de planos.
        /// </summary>
        private static IColor[] PaletaCategorica(int n)
        {
            var salida = new IColor[n];
            for (int i = 0; i < n; i++)
            {
                IHsvColor hsv = new HsvColorClass
                {
                    Hue = (int)Math.Round(360.0 * i / n) % 360,
                    Saturation = 70,
                    Value = 85
                };
                salida[i] = (IColor)hsv;
            }
            return salida;
        }

        private static double[] LeerValores(JToken t, string nombre)
        {
            if (t == null || t.Type == JTokenType.Null)
                return null;
            JArray arr = t as JArray;
            if (arr == null)
                throw new ArgumentException("'" + nombre + "' 必须是数字列表。");
            var salida = new double[arr.Count];
            for (int i = 0; i < arr.Count; i++)
            {
                if (arr[i].Type != JTokenType.Integer && arr[i].Type != JTokenType.Float)
                    throw new ArgumentException("'" + nombre + "[" + i + "]' 不是数字：" + arr[i]);
                salida[i] = (double)arr[i];
            }
            return salida;
        }

        private static JObject AplicarEstirado(IRasterLayer rl, IRaster raster,
            IColor desde, IColor hasta, esriColorRampAlgorithm algoritmo)
        {
            IRasterStretchColorRampRenderer estirado = new RasterStretchColorRampRendererClass();
            IRasterRenderer render = (IRasterRenderer)estirado;

            render.Raster = raster;

            IAlgorithmicColorRamp rampa = new AlgorithmicColorRampClass
            {
                Algorithm = algoritmo,
                FromColor = desde,
                ToColor = hasta,
                Size = 255
            };
            bool rampaOk;
            rampa.CreateRamp(out rampaOk);
            if (!rampaOk)
                throw new ArgumentException("无法用给定的颜色创建色带。");

            estirado.BandIndex = 0;
            estirado.ColorRamp = rampa;
            try
            {
                render.Update();
            }
            catch (Exception ex)
            {
                throw new ArgumentException("无法应用拉伸：" + ex.Message
                    + "。通常是因为该栅格未计算统计量。");
            }
            rl.Renderer = render;

            return new JObject
            {
                ["banda"] = 0,
            };
        }

        /// <summary>
        /// Calcula estadísticas de las bandas si faltan. Sin ellas, el renderer
        /// clasificado falla con un E_FAIL de COM que no explica nada.
        /// </summary>
        private static void AsegurarEstadisticas(IRaster raster)
        {
            IRasterBandCollection bandas = raster as IRasterBandCollection;
            if (bandas == null)
                return;
            for (int i = 0; i < bandas.Count; i++)
            {
                IRasterBand banda = bandas.Item(i);
                bool tiene;
                banda.HasStatistics(out tiene);
                if (tiene)
                    continue;
                try
                {
                    banda.ComputeStatsAndHist();
                    Log.Info("已计算栅格第 " + i + " 波段的统计量。");
                }
                catch (Exception ex)
                {
                    // No es fatal: puede ser una fuente de solo lectura. Se deja que
                    // falle después con su mensaje, pero queda anotado el motivo.
                    Log.Error("无法计算栅格第 " + i, ex);
                }
            }
        }

        /// <summary>
        /// Traduce el nombre del algoritmo de rampa. Por defecto CIE Lab, NO HSV.
        ///
        /// El motivo, medido el 2026-09-04: `esriHSVAlgorithm` interpola el TONO
        /// entre los dos extremos recorriendo la rueda de color, y pasa por todos
        /// los tonos intermedios. De rojo oscuro (~352°) a rosa pálido (~19°),
        /// separados 27° por el lado corto, salía rojo → morado → turquesa →
        /// verde → rosa: un arcoíris del que no se puede leer ningún orden. Con
        /// tres pares de extremos distintos, los tres en arcoíris.
        ///
        /// CIE Lab interpola en un espacio perceptualmente uniforme: no da vueltas
        /// por la rueda y el resultado es una secuencia que sí se lee como orden,
        /// que es justo lo que necesita la cartografía cuantitativa (NDVI,
        /// anomalías, FCC, P95, pendientes). Se deja HSV alcanzable por si alguien
        /// lo quiere a propósito, pero deja de ser el comportamiento por defecto.
        /// </summary>
        private static esriColorRampAlgorithm LeerAlgoritmo(JToken t)
        {
            string nombre = ((string)t ?? "cielab").ToLowerInvariant().Replace(" ", "");
            switch (nombre)
            {
                case "cielab":
                case "lab":
                    return esriColorRampAlgorithm.esriCIELabAlgorithm;
                case "lablch":
                case "lch":
                    return esriColorRampAlgorithm.esriLabLChAlgorithm;
                case "hsv":
                    return esriColorRampAlgorithm.esriHSVAlgorithm;
                default:
                    throw new ArgumentException("'algoritmo' 必须为 'cielab'（默认）、"
                        + "'lablch' 或 'hsv'。收到值：" + nombre
                        + "。注意 'hsv'：它插值时会绕色轮一圈，"
                        + "产生彩虹色而非可读的渐变。");
            }
        }

        private static IColor[] ConstruirRampa(IColor desde, IColor hasta, int n,
            esriColorRampAlgorithm algoritmo)
        {
            IAlgorithmicColorRamp rampa = new AlgorithmicColorRampClass
            {
                Algorithm = algoritmo,
                FromColor = desde,
                ToColor = hasta,
                Size = n
            };
            bool ok;
            rampa.CreateRamp(out ok);
            if (!ok)
                throw new ArgumentException("无法用给定的颜色创建色带。");

            IEnumColors enumerados = rampa.Colors;
            enumerados.Reset();
            var salida = new IColor[n];
            for (int i = 0; i < n; i++)
                salida[i] = enumerados.Next() ?? hasta;
            return salida;
        }

        /// <summary>
        /// Lee `colores`: una lista de N colores [R,G,B], uno por clase. Devuelve
        /// null si no se ha dado, para que quien llama caiga a la rampa.
        /// </summary>
        private static IColor[] LeerPaleta(JToken t, int nClases)
        {
            JArray arr = t as JArray;
            if (arr == null || arr.Count == 0)
                return null;
            if (arr.Count != nClases)
                throw new ArgumentException("'colores' 提供了 " + arr.Count + " 个颜色，而分类结果是 " + nClases
                    + " 个类别。两者数量必须一致，或者不传该参数改用色带。");
            var salida = new IColor[nClases];
            for (int i = 0; i < nClases; i++)
                salida[i] = LeerColor(arr[i], 128, 128, 128);
            return salida;
        }

        /// <summary>
        /// Lee `etiquetas`: los rótulos de leyenda, uno por clase. Cuando los
        /// cortes vienen de percentiles o de una reclasificación, el número del
        /// corte no dice nada útil ("1 – 2") y el rótulo que sirve es el de
        /// significado ("Defoliación fuerte"). Null si no se ha dado.
        /// </summary>
        private static string[] LeerEtiquetas(JToken t, int nClases)
        {
            JArray arr = t as JArray;
            if (arr == null || arr.Count == 0)
                return null;
            if (arr.Count != nClases)
                throw new ArgumentException("'etiquetas' 提供了 " + arr.Count + " 个标签，而分类结果是 " + nClases
                    + " 个类别。两者数量必须一致。");
            var salida = new string[nClases];
            for (int i = 0; i < nClases; i++)
                salida[i] = (string)arr[i] ?? "";
            return salida;
        }

        private static string Etiqueta(double valor)
        {
            return valor.ToString(Math.Abs(valor) >= 100 ? "0.#" : "0.###",
                CultureInfo.InvariantCulture);
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

        private static int LeerInt(JToken t, int porDefecto)
        {
            return t == null || t.Type == JTokenType.Null ? porDefecto : (int)t;
        }
    }
}
