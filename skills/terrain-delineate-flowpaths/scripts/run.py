# -*- coding: utf-8 -*-
"""
按出口面划分汇水区 —— ArcMap 版

由 DEM 算 D8 流向，再以一个或多个**出口面**（洼地、库塘、研究区边界开口等面要素）为倾泻点划分汇水区，输出每个出口对应的集水多边形。用于小流域/汇水单元快速圈定。

参数顺序（按地理处理工具原定义）：
  1. 输入 DEM 栅格
  2. 出口面要素类（每个面 = 一个汇水区出口）
  3. 输出汇水区面要素

用法：
    python run.py <输入 DEM 栅格> <出口面要素类（每个面 = 一个汇水区出口）> <输出汇水区面要素>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import arcpy


def _u(v):
    if v is None:
        return u''
    if isinstance(v, bytes):
        for enc in (u'mbcs', u'utf-8', u'gbk', u'latin-1'):
            try:
                return v.decode(enc)
            except Exception:
                continue
        return v.decode(u'utf-8', u'replace')
    return u'%s' % v


def _split(text):
    t = (text or u'').strip()
    if not t or t == u'#':
        return []
    return [p.strip() for p in t.replace(u',', u';').split(u';') if p.strip()]


def _has_field(ds, name):
    for f in arcpy.ListFields(ds):
        if f.name.upper() == name.upper():
            return True
    return False




# ------------------------------------------------------------------ 运行入口
def _to_unicode(s):
    """py2 下 sys.argv 是字节串，中文参数不解码会和 u"" 比较炸，入口统一转 unicode。"""
    if not isinstance(s, bytes):
        return s
    for enc in (u"mbcs", u"utf-8", u"gbk", u"latin-1"):
        try:
            return s.decode(enc)
        except Exception:
            continue
    return s.decode(u"utf-8", u"replace")


def main(argv):
    if len(argv) < 3:
        print(u"用法: python run.py <输入 DEM 栅格> <出口面要素类（每个面 = 一个汇水区出口）> <输出汇水区面要素>")
        return 1
    dem = argv[0]
    sink_poly = argv[1]
    out_fc = argv[2]
    if arcpy.CheckExtension(u'spatial') != u'Available':
        raise RuntimeError(u"需要 Spatial Analyst 扩展许可")
    arcpy.CheckOutExtension(u'spatial')
    try:
        arcpy.env.overwriteOutput = True
        dem_ras = arcpy.Raster(dem)
        arcpy.env.extent = dem_ras.extent
        arcpy.env.snapRaster = dem
        arcpy.env.cellSize = float(dem_ras.meanCellWidth)

        fdr = arcpy.sa.FlowDirection(dem_ras)
        oid_f = arcpy.Describe(sink_poly).OIDFieldName
        sink_ras = r'in_memory\sink_ras'
        arcpy.PolygonToRaster_conversion(sink_poly, oid_f, sink_ras,
                                         u'CELL_CENTER', u'NONE',
                                         float(dem_ras.meanCellWidth))
        ws = arcpy.sa.Watershed(fdr, sink_ras, u'VALUE')
        arcpy.RasterToPolygon_conversion(ws, out_fc, u'NO_SIMPLIFY', u'VALUE')
        try:
            arcpy.Delete_management(sink_ras)
        except Exception:
            pass
        cnt = arcpy.GetCount_management(out_fc).getOutput(0)
        print(u"汇水区 -> %s（%s 个，gridcode=出口面 OID）" % (out_fc, cnt))
    finally:
        arcpy.CheckInExtension(u'spatial')
    print(u"完成")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main([_to_unicode(v) for v in sys.argv[1:]]))
    except Exception as e:
        try:
            print(u"ERROR: %s" % e)
        except Exception:
            pass
        raise
