using System;
using System.Collections.Generic;
using System.Linq;
using ESRI.ArcGIS.ArcMapUI;
using ESRI.ArcGIS.Carto;
using ESRI.ArcGIS.Framework;
using Newtonsoft.Json.Linq;

namespace YghsBridge.AddIn.Handlers
{
    /// <summary>
    /// set_text_element / list_layout_elements — contrato JSON que esperan los
    /// schemas del servidor MCP. Lógica de selección de set_text_element:
    /// selector 'nombre' (name del elemento) o 'buscar' (texto actual; exacto
    /// primero, subcadena después; ambigüedad = error que lista coincidencias).
    /// list_layout_elements devuelve los mismos nombres de clase que arcpy
    /// (TextElement, LegendElement, ...) y acepta los mismos filtros tipo/patron.
    /// </summary>
    internal static class LayoutHandlers
    {
        // Tipos arcpy admitidos en el filtro 'tipo' -> nombre de clase del item.
        private static readonly Dictionary<string, string> _tiposArcpy =
            new Dictionary<string, string>
            {
                { "TEXT_ELEMENT",        "TextElement" },
                { "LEGEND_ELEMENT",      "LegendElement" },
                { "PICTURE_ELEMENT",     "PictureElement" },
                { "MAPSURROUND_ELEMENT", "MapsurroundElement" },
                { "DATAFRAME_ELEMENT",   "DataFrameElement" },
                { "GRAPHIC_ELEMENT",     "GraphicElement" },
            };

        public static JObject ListLayoutElements(JObject parameters)
        {
            string tipo = (string)parameters["tipo"];
            string patron = (string)parameters["patron"];
            if (!string.IsNullOrEmpty(tipo))
            {
                tipo = tipo.ToUpperInvariant();
                if (!_tiposArcpy.ContainsKey(tipo))
                    throw new ArgumentException("无效类型：" + tipo
                        + "。允许的类型：" + string.Join(", ", _tiposArcpy.Keys));
            }

            System.Text.RegularExpressions.Regex regexPatron = null;
            if (!string.IsNullOrEmpty(patron) && patron != "*")
            {
                // Traducción wildcard -> regex (equivalente al fnmatch de Python).
                string rx = "^" + System.Text.RegularExpressions.Regex.Escape(patron)
                    .Replace(@"\*", ".*").Replace(@"\?", ".") + "$";
                regexPatron = new System.Text.RegularExpressions.Regex(
                    rx, System.Text.RegularExpressions.RegexOptions.IgnoreCase);
            }

            IApplication app = ArcSession.App();
            IMxDocument doc = ArcSession.Doc(app);

            var elementos = new JArray();
            IGraphicsContainer gc = (IGraphicsContainer)doc.PageLayout;
            gc.Reset();
            IElement el;
            while ((el = gc.Next()) != null)
            {
                string clase = ClasificarElemento(el);
                if (tipo != null && _tiposArcpy[tipo] != clase)
                    continue;
                IElementProperties props = el as IElementProperties;
                string nombre = props != null ? (props.Name ?? "") : "";
                if (regexPatron != null && !regexPatron.IsMatch(nombre))
                    continue;
                var item = new JObject { ["nombre"] = nombre, ["tipo"] = clase };
                ITextElement te = el as ITextElement;
                if (te != null)
                    item["texto"] = te.Text;
                elementos.Add(item);
            }

            return Protocol.Result(new JObject
            {
                ["num"] = elementos.Count,
                ["elementos"] = elementos
            });
        }

        private static string ClasificarElemento(IElement el)
        {
            if (el is ITextElement)
                return "TextElement";
            if (el is IMapFrame)
                return "DataFrameElement";
            IMapSurroundFrame msf = el as IMapSurroundFrame;
            if (msf != null)
                return msf.MapSurround is ILegend ? "LegendElement" : "MapsurroundElement";
            if (el is IPictureElement)
                return "PictureElement";
            return "GraphicElement";
        }

        public static JObject SetTextElement(JObject parameters)
        {
            string nombre = (string)parameters["nombre"];
            string buscar = (string)parameters["buscar"];
            string texto = (string)parameters["texto"] ?? "";

            IApplication app = ArcSession.App();
            IMxDocument doc = ArcSession.Doc(app);

            var elementos = new List<KeyValuePair<ITextElement, string>>(); // elemento + name
            IGraphicsContainer gc = (IGraphicsContainer)doc.PageLayout;
            gc.Reset();
            IElement el;
            while ((el = gc.Next()) != null)
            {
                ITextElement te = el as ITextElement;
                if (te == null)
                    continue;
                IElementProperties props = el as IElementProperties;
                elementos.Add(new KeyValuePair<ITextElement, string>(te, props != null ? props.Name : ""));
            }

            ITextElement objetivo = null;
            string nombreObjetivo = null;

            if (!string.IsNullOrEmpty(nombre))
            {
                foreach (var par in elementos)
                {
                    if (par.Value == nombre)
                    {
                        objetivo = par.Key;
                        nombreObjetivo = par.Value;
                        break;
                    }
                }
                if (objetivo == null)
                {
                    string disponibles = string.Join(", ",
                        elementos.Where(p => !string.IsNullOrEmpty(p.Value)).Select(p => p.Value));
                    throw new ArgumentException(
                        "未按名称找到文本元素：" + nombre
                        + "。可用的命名元素："
                        + (disponibles.Length > 0 ? disponibles : "(无)"));
                }
            }
            else if (buscar != null)
            {
                var exactos = elementos.Where(p => p.Key.Text == buscar).ToList();
                var candidatos = exactos.Count > 0
                    ? exactos
                    : elementos.Where(p => (p.Key.Text ?? "").Contains(buscar)).ToList();
                if (candidatos.Count == 0)
                    throw new ArgumentException("没有文本元素匹配：" + buscar);
                if (candidatos.Count > 1)
                {
                    string textos = string.Join(" | ", candidatos.Select(p => p.Key.Text));
                    throw new ArgumentException(
                        "有多个元素匹配 " + buscar + "（共 " + candidatos.Count
                        + " 个）。请把 'buscar' 写得更精确，或直接用 'nombre' 指定元素。匹配项：" + textos);
                }
                objetivo = candidatos[0].Key;
                nombreObjetivo = candidatos[0].Value;
            }
            else
            {
                throw new ArgumentException(
                    "请提供 'nombre'（元素名称）或 'buscar'（元素当前文本）。");
            }

            string anterior = objetivo.Text;
            objetivo.Text = texto;

            // Refrescar la capa de gráficos del layout y la vista activa.
            IActiveView layoutView = (IActiveView)doc.PageLayout;
            layoutView.PartialRefresh(esriViewDrawPhase.esriViewGraphics, null, null);
            doc.ActiveView.Refresh();

            return Protocol.Result(new JObject
            {
                ["nombre"] = nombreObjetivo,
                ["texto_anterior"] = anterior,
                ["texto_nuevo"] = texto
            });
        }
    }
}
