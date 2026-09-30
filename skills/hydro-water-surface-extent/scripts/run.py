# -*- coding: utf-8 -*-
"""
按去趋势高度圈水面范围 —— ArcMap 版

对去趋势 DEM 取「低于某高度阈值」的连通区域转成面，并做 PAEK 平滑去掉栅格锯齿，输出水面/滩地范围多边形。配合 `hydro-detrend-dem`：阈值 0.5 就是"高出河谷底面 0.5 米以内的淹没范围"。

参数顺序（按地理处理工具原定义）：
  1. 输入去趋势 DEM（hydro-detrend-dem 的产物）
  2. 高度阈值（去趋势值 <= 该值的区域划入水面）
  3. 面平滑容差（0 = 不平滑；一般取 1~2 个像元大小）
  4. 输出水面范围面要素

用法：
    python run.py <输入去趋势 DEM（hydro-detrend-dem 的产物）> <高度阈值（去趋势值 <= 该值的区域划入水面）> <面平滑容差（0 = 不平滑；一般取 1~2 个像元大小）> <输出水面范围面要素>
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
        print(u"用法: python run.py <输入去趋势 DEM（hydro-detrend-dem 的产物）> <高度阈值（去趋势值 <= 该值的区域划入水面）> <面平滑容差（0 = 不平滑；一般取 1~2 个像元大小）> <输出水面范围面要素>")
        return 1
    detrend_dem = argv[0]
    threshold = float(argv[1])
    smooth_tol = float(argv[2])
    out_fc = argv[3]
    if arcpy.CheckExtension('spatial') != 'Available':
        raise RuntimeError(u"需要 Spatial Analyst 扩展许可")
    arcpy.CheckOutExtension('spatial')
    try:
        arcpy.env.overwriteOutput = True
        # RasterToPolygon 只收整型栅格：SetNull 给常量 1 做掩膜再 Int 化
        kept = arcpy.sa.Int(arcpy.sa.SetNull(
            arcpy.Raster(detrend_dem) > threshold, 1))
        sgdb = arcpy.env.scratchGDB
        poly_raw = os.path.join(sgdb, u'wse_raw')
        arcpy.RasterToPolygon_conversion(kept, poly_raw, "NO_SIMPLIFY", "VALUE")
        if smooth_tol and smooth_tol > 0:
            try:
                arcpy.SmoothPolygon_cartography(poly_raw, out_fc, "PAEK",
                                                smooth_tol)
            except Exception:
                arcpy.CopyFeatures_management(poly_raw, out_fc)
                print(u"平滑失败，已输出未平滑边界")
        else:
            arcpy.CopyFeatures_management(poly_raw, out_fc)
        try:
            arcpy.Delete_management(poly_raw)
        except Exception:
            pass
        cnt = arcpy.GetCount_management(out_fc).getOutput(0)
        print(u"水面范围 -> %s（%s 个连通面，阈值 %g）"
              % (out_fc, cnt, threshold))
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
