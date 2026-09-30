# -*- coding: utf-8 -*-
"""
由河道面提取中心线 —— ArcMap 版

把河道/湖库水面多边形栅格化后做形态学细化（Thin），得到单像素宽的骨架线再转成矢量线并做 PAEK 平滑，输出河道中心线。用于从水面范围反推深泓线/航道中心线、给河流做纵剖面与里程量算的基准线。

参数顺序（按地理处理工具原定义）：
  1. 河道面要素（水面/河岸多边形）
  2. 栅格化像元大小（坐标系单位，如米；越小越细但越慢）
  3. PAEK 平滑容差（一般 2~5，单位同坐标系）
  4. 输出中心线要素

用法：
    python run.py <河道面要素（水面/河岸多边形）> <栅格化像元大小（坐标系单位，如米；越小越细但越慢）> <PAEK 平滑容差（一般 2~5，单位同坐标系）> <输出中心线要素>
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
    if len(argv) < 4:
        print(u"用法: python run.py <河道面要素（水面/河岸多边形）> <栅格化像元大小（坐标系单位，如米；越小越细但越慢）> <PAEK 平滑容差（一般 2~5，单位同坐标系）> <输出中心线要素>")
        return 1
    banks_poly = argv[0]
    cell_size = float(argv[1])
    smooth_tol = float(argv[2])
    out_fc = argv[3]
    if arcpy.CheckExtension('spatial') != 'Available':
        raise RuntimeError(u"需要 Spatial Analyst 扩展许可")
    arcpy.CheckOutExtension('spatial')
    try:
        arcpy.env.overwriteOutput = True
        if cell_size <= 0:
            raise ValueError(u"像元大小必须大于 0")
        sr = arcpy.Describe(banks_poly).spatialReference
        arcpy.env.cellSize = cell_size
        arcpy.env.extent = banks_poly
        arcpy.env.mask = banks_poly
        arcpy.env.outputCoordinateSystem = sr

        sgdb = arcpy.env.scratchGDB
        banks_ras = os.path.join(sgdb, u'hcl_banks')
        oid_f = arcpy.Describe(banks_poly).OIDFieldName
        arcpy.PolygonToRaster_conversion(banks_poly, oid_f, banks_ras)

        thin = arcpy.sa.Thin(banks_ras, "ZERO", "FILTER", "ROUND")
        cl_raw = os.path.join(sgdb, u'hcl_raw')
        arcpy.RasterToPolyline_conversion(thin, cl_raw, "ZERO",
                                          cell_size, "SIMPLIFY")
        arcpy.SmoothLine_cartography(cl_raw, out_fc, "PAEK", smooth_tol)
        for t in (banks_ras, cl_raw):
            try:
                arcpy.Delete_management(t)
            except Exception:
                pass
        cnt = arcpy.GetCount_management(out_fc).getOutput(0)
        print(u"中心线 -> %s（%s 条，像元 %g，平滑 %g）"
              % (out_fc, cnt, cell_size, smooth_tol))
        if int(cnt) == 0:
            print(u"提示: 没提出中心线，多半是像元太大（河道被栅格化没了），调小 cell_size")
    finally:
        arcpy.CheckInExtension('spatial')
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
