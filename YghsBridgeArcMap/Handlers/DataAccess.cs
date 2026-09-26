using System;
using System.IO;
using ESRI.ArcGIS.Carto;
using ESRI.ArcGIS.DataSourcesFile;
using ESRI.ArcGIS.DataSourcesGDB;
using ESRI.ArcGIS.DataSourcesRaster;
using ESRI.ArcGIS.Geodatabase;
using Newtonsoft.Json.Linq;

namespace YghsBridge.AddIn.Handlers
{
    /// <summary>
    /// Utilidades compartidas de acceso a datos para los handlers de capas+datos:
    /// apertura de workspaces (carpeta shapefile / file gdb / ráster), creación de
    /// capas desde ruta y mapeo de los enums ArcObjects al vocabulario arcpy que
    /// usa el contrato JSON del servidor MCP ("String", "Polygon", "FeatureClass"...).
    /// </summary>
    internal static class DataAccess
    {
        private static readonly string[] ExtensionesRaster =
            { ".tif", ".tiff", ".img", ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".sid", ".ecw", ".jp2", ".asc" };

        public static bool EsExtensionRaster(string ext)
        {
            return Array.IndexOf(ExtensionesRaster, (ext ?? "").ToLowerInvariant()) >= 0;
        }

        /// <summary>Abre un workspace: ".gdb" → FileGDB; carpeta → shapefiles o
        /// rásteres de archivo según paraRasters. Error accionable si no existe.</summary>
        public static IWorkspace AbrirWorkspace(string ruta, bool paraRasters)
        {
            if (string.IsNullOrEmpty(ruta))
                throw new ArgumentException("请提供 'workspace'，或先用 set_workspace 固定工作空间。");
            if (!Directory.Exists(ruta))
                throw new ArgumentException("未找到工作空间（文件夹或 .gdb）：" + ruta);

            IWorkspaceFactory factory;
            if (ruta.TrimEnd('\\', '/').ToLowerInvariant().EndsWith(".gdb"))
                factory = new FileGDBWorkspaceFactoryClass();
            else if (paraRasters)
                factory = new RasterWorkspaceFactoryClass();
            else
                factory = new ShapefileWorkspaceFactoryClass();
            return factory.OpenFromFile(ruta, 0);
        }

        /// <summary>Divide una ruta a dataset de gdb en (ruta de la .gdb, nombre del
        /// dataset = último segmento). Los nombres de fc son únicos en toda la gdb,
        /// también dentro de feature datasets.</summary>
        public static bool SepararRutaGdb(string ruta, out string gdb, out string nombre)
        {
            gdb = null;
            nombre = null;
            int idx = ruta.ToLowerInvariant().IndexOf(".gdb", StringComparison.Ordinal);
            if (idx < 0)
                return false;
            gdb = ruta.Substring(0, idx + 4);
            string resto = ruta.Substring(idx + 4).Trim('\\', '/');
            if (resto.Length == 0)
                return false;
            int corte = resto.LastIndexOfAny(new[] { '\\', '/' });
            nombre = corte >= 0 ? resto.Substring(corte + 1) : resto;
            return true;
        }

        /// <summary>Crea una ILayer desde una ruta en disco: .shp, feature class o
        /// ráster de file gdb, o ráster de archivo — equivalente al arcpy.mapping.Layer(ruta).</summary>
        public static ILayer CrearCapaDesdeRuta(string fuente)
        {
            string ext = Path.GetExtension(fuente ?? "").ToLowerInvariant();
            string gdb, nombre;

            if (ext == ".shp")
            {
                if (!File.Exists(fuente))
                    throw new ArgumentException("不存在该 shapefile：" + fuente);
                IWorkspace ws = AbrirWorkspace(Path.GetDirectoryName(fuente), false);
                IFeatureClass fc = ((IFeatureWorkspace)ws).OpenFeatureClass(Path.GetFileNameWithoutExtension(fuente));
                return CapaDesdeFeatureClass(fc);
            }

            if (SepararRutaGdb(fuente, out gdb, out nombre))
            {
                if (!Directory.Exists(gdb))
                    throw new ArgumentException("不存在该地理数据库：" + gdb);
                IWorkspace ws = AbrirWorkspace(gdb, false);
                try
                {
                    IFeatureClass fc = ((IFeatureWorkspace)ws).OpenFeatureClass(nombre);
                    return CapaDesdeFeatureClass(fc);
                }
                catch (Exception)
                {
                    // No es feature class: probar como ráster de gdb antes de rendirse.
                    IRasterWorkspaceEx rwx = ws as IRasterWorkspaceEx;
                    if (rwx == null)
                        throw;
                    IRasterDataset rd = rwx.OpenRasterDataset(nombre);
                    IRasterLayer rl = new RasterLayerClass();
                    rl.CreateFromDataset(rd);
                    return (ILayer)rl;
                }
            }

            if (EsExtensionRaster(ext))
            {
                if (!File.Exists(fuente))
                    throw new ArgumentException("不存在该栅格：" + fuente);
                IRasterLayer rl = new RasterLayerClass();
                rl.CreateFromFilePath(fuente);
                return (ILayer)rl;
            }

            throw new ArgumentException(
                "不支持的源（支持 .shp、.gdb 中的要素类/栅格，或文件栅格）：" + fuente);
        }

        private static ILayer CapaDesdeFeatureClass(IFeatureClass fc)
        {
            IFeatureLayer fl = new FeatureLayerClass();
            fl.FeatureClass = fc;
            fl.Name = ((IDataset)fc).Name;
            return (ILayer)fl;
        }

        /// <summary>Ruta completa de la fuente de una capa (workspace + dataset),
        /// equivalente al catalogPath/dataSource de arcpy. Null si no es resoluble.</summary>
        public static string RutaFuente(ILayer lyr, out string workspace)
        {
            workspace = null;
            try
            {
                IDataLayer dataLayer = lyr as IDataLayer;
                IDatasetName dsn = dataLayer != null ? dataLayer.DataSourceName as IDatasetName : null;
                if (dsn == null)
                    return null;
                IWorkspaceName wsn = dsn.WorkspaceName;
                workspace = wsn != null ? wsn.PathName : null;
                return workspace != null ? Path.Combine(workspace, dsn.Name) : dsn.Name;
            }
            catch
            {
                return null; // capas sin fuente resoluble (servicios, rotas sin name object)
            }
        }

        /// <summary>Nombre arcpy del tipo de campo (el Field.type de arcpy).</summary>
        public static string NombreTipoCampo(esriFieldType tipo)
        {
            switch (tipo)
            {
                case esriFieldType.esriFieldTypeSmallInteger: return "SmallInteger";
                case esriFieldType.esriFieldTypeInteger: return "Integer";
                case esriFieldType.esriFieldTypeSingle: return "Single";
                case esriFieldType.esriFieldTypeDouble: return "Double";
                case esriFieldType.esriFieldTypeString: return "String";
                case esriFieldType.esriFieldTypeDate: return "Date";
                case esriFieldType.esriFieldTypeOID: return "OID";
                case esriFieldType.esriFieldTypeGeometry: return "Geometry";
                case esriFieldType.esriFieldTypeBlob: return "Blob";
                case esriFieldType.esriFieldTypeRaster: return "Raster";
                case esriFieldType.esriFieldTypeGUID: return "GUID";
                case esriFieldType.esriFieldTypeGlobalID: return "GlobalID";
                case esriFieldType.esriFieldTypeXML: return "XML";
                default: return tipo.ToString();
            }
        }

        /// <summary>Nombre arcpy del tipo de geometría (el Describe.shapeType de arcpy).</summary>
        public static string NombreTipoGeometria(ESRI.ArcGIS.Geometry.esriGeometryType tipo)
        {
            switch (tipo)
            {
                case ESRI.ArcGIS.Geometry.esriGeometryType.esriGeometryPoint: return "Point";
                case ESRI.ArcGIS.Geometry.esriGeometryType.esriGeometryMultipoint: return "Multipoint";
                case ESRI.ArcGIS.Geometry.esriGeometryType.esriGeometryPolyline: return "Polyline";
                case ESRI.ArcGIS.Geometry.esriGeometryType.esriGeometryPolygon: return "Polygon";
                case ESRI.ArcGIS.Geometry.esriGeometryType.esriGeometryMultiPatch: return "MultiPatch";
                default: return tipo.ToString();
            }
        }

        /// <summary>Nombre arcpy del tipo de dataset (el Describe.datasetType de arcpy).</summary>
        public static string NombreTipoDataset(esriDatasetType tipo)
        {
            switch (tipo)
            {
                case esriDatasetType.esriDTFeatureClass: return "FeatureClass";
                case esriDatasetType.esriDTFeatureDataset: return "FeatureDataset";
                case esriDatasetType.esriDTTable: return "Table";
                case esriDatasetType.esriDTRasterDataset: return "RasterDataset";
                case esriDatasetType.esriDTRasterCatalog: return "RasterCatalog";
                default: return tipo.ToString();
            }
        }

        /// <summary>Valor de atributo COM → JSON. Las fechas van como texto para no
        /// depender de la serialización por defecto de Json.NET.</summary>
        public static JToken ValorAJson(object v)
        {
            if (v == null || v is DBNull)
                return JValue.CreateNull();
            if (v is DateTime)
                return ((DateTime)v).ToString("yyyy-MM-dd HH:mm:ss");
            try
            {
                return new JValue(v);
            }
            catch
            {
                return v.ToString();
            }
        }

        /// <summary>Combina definition query y where en un solo predicado SQL.</summary>
        public static string CombinarWhere(string defQuery, string where)
        {
            bool hayDq = !string.IsNullOrEmpty(defQuery);
            bool hayWhere = !string.IsNullOrEmpty(where);
            if (hayDq && hayWhere)
                return "(" + defQuery + ") AND (" + where + ")";
            return hayDq ? defQuery : (hayWhere ? where : null);
        }
    }
}
