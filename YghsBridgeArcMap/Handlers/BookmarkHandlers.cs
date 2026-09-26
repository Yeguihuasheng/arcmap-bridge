using System;
using ESRI.ArcGIS.ArcMapUI;
using ESRI.ArcGIS.Carto;
using ESRI.ArcGIS.Geometry;
using Newtonsoft.Json.Linq;

namespace YghsBridge.AddIn.Handlers
{
    /// <summary>
    /// Marcadores espaciales (bookmarks) del documento.
    ///
    /// Posible desde la migración a .NET, que da acceso a ArcObjects: IMapBookmarks
    /// sobre el IMap. El equivalente en el MCP de QGIS (add_bookmark/get_bookmarks)
    /// existía desde siempre y aquí no, así que esto cierra esa asimetría.
    /// </summary>
    internal static class BookmarkHandlers
    {
        public static JObject GetBookmarks(JObject parameters)
        {
            IMxDocument doc;
            IMap map = MapHandlers.FocusMap(out doc);
            IMapBookmarks marcadores = map as IMapBookmarks;
            if (marcadores == null)
                throw new ArgumentException("此数据框不支持书签。");

            var lista = new JArray();
            IEnumSpatialBookmark e = marcadores.Bookmarks;
            e.Reset();
            ISpatialBookmark bm;
            while ((bm = e.Next()) != null)
            {
                var fila = new JObject { ["nombre"] = bm.Name };
                IAOIBookmark aoi = bm as IAOIBookmark;
                if (aoi != null && aoi.Location != null)
                {
                    IEnvelope env = aoi.Location;
                    fila["extent"] = new JArray { env.XMin, env.YMin, env.XMax, env.YMax };
                }
                lista.Add(fila);
            }

            return Protocol.Result(new JObject
            {
                ["data_frame"] = map.Name,
                ["num"] = lista.Count,
                ["marcadores"] = lista,
            });
        }

        public static JObject AddBookmark(JObject parameters)
        {
            string nombre = (string)parameters["nombre"];
            if (string.IsNullOrEmpty(nombre))
                throw new ArgumentException("请提供 'nombre'（书签名称）。");

            IMxDocument doc;
            IMap map = MapHandlers.FocusMap(out doc);
            IMapBookmarks marcadores = map as IMapBookmarks;
            if (marcadores == null)
                throw new ArgumentException("此数据框不支持书签。");

            IActiveView vista = (IActiveView)map;
            IEnvelope extent = vista.Extent;
            if (extent == null || extent.IsEmpty)
                throw new ArgumentException("视图没有范围：请先添加图层并缩放到目标区域，再保存书签。");

            // Un nombre repetido crearía dos marcadores indistinguibles en el menú,
            // así que se reemplaza en vez de duplicar.
            bool reemplazado = QuitarSiExiste(marcadores, nombre);

            IAOIBookmark marcador = new AOIBookmarkClass();
            marcador.Location = extent.Envelope;
            ISpatialBookmark spatial = (ISpatialBookmark)marcador;
            spatial.Name = nombre;
            marcadores.AddBookmark(spatial);

            return Protocol.Result(new JObject
            {
                ["nombre"] = nombre,
                ["reemplazado"] = reemplazado,
                ["extent"] = new JArray { extent.XMin, extent.YMin, extent.XMax, extent.YMax },
            });
        }

        public static JObject RemoveBookmark(JObject parameters)
        {
            string nombre = (string)parameters["nombre"];
            if (string.IsNullOrEmpty(nombre))
                throw new ArgumentException("请提供要删除的书签名称 'nombre'。");

            IMxDocument doc;
            IMap map = MapHandlers.FocusMap(out doc);
            IMapBookmarks marcadores = map as IMapBookmarks;
            if (marcadores == null)
                throw new ArgumentException("此数据框不支持书签。");

            if (!QuitarSiExiste(marcadores, nombre))
                throw new ArgumentException("没有名为 '" + nombre + "'.");

            return Protocol.Result(new JObject { ["nombre"] = nombre, ["borrado"] = true });
        }

        public static JObject GotoBookmark(JObject parameters)
        {
            string nombre = (string)parameters["nombre"];
            if (string.IsNullOrEmpty(nombre))
                throw new ArgumentException("请提供要跳转到的书签名称 'nombre'。");

            IMxDocument doc;
            IMap map = MapHandlers.FocusMap(out doc);
            IMapBookmarks marcadores = map as IMapBookmarks;
            if (marcadores == null)
                throw new ArgumentException("此数据框不支持书签。");

            ISpatialBookmark encontrado = Buscar(marcadores, nombre);
            if (encontrado == null)
                throw new ArgumentException("没有名为 '" + nombre
                    + "' 的书签。可用 get_bookmarks 查看现有书签。");

            encontrado.ZoomTo(map);
            IActiveView vista = (IActiveView)map;
            vista.Refresh();

            IEnvelope env = vista.Extent;
            return Protocol.Result(new JObject
            {
                ["nombre"] = nombre,
                ["extent"] = new JArray { env.XMin, env.YMin, env.XMax, env.YMax },
            });
        }

        private static ISpatialBookmark Buscar(IMapBookmarks marcadores, string nombre)
        {
            IEnumSpatialBookmark e = marcadores.Bookmarks;
            e.Reset();
            ISpatialBookmark bm;
            while ((bm = e.Next()) != null)
            {
                if (string.Equals(bm.Name, nombre, StringComparison.OrdinalIgnoreCase))
                    return bm;
            }
            return null;
        }

        private static bool QuitarSiExiste(IMapBookmarks marcadores, string nombre)
        {
            ISpatialBookmark bm = Buscar(marcadores, nombre);
            if (bm == null)
                return false;
            marcadores.RemoveBookmark(bm);
            return true;
        }
    }
}
