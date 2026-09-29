# -*- coding: utf-8 -*-
"""
闭合线转面 —— ArcMap 版

把闭合的线要素转成面要素类，保留原始坐标系，常用于把 CAD 导入的闭合多段线、地类界线转成图斑面。

参数顺序（按地理处理工具原定义）：
  1. 输入线要素类
  2. 输出面要素类

用法：
    python run.py <输入线要素类> <输出面要素类>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import arcpy







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
    if len(argv) < 2:
        print(u"用法: python run.py <输入线要素类> <输出面要素类>")
        return 1
    in_polylines = argv[0]
    out_polygon = argv[1]
    arcpy.env.overwriteOutput = True
    desc = arcpy.Describe(in_polylines)
    if desc.shapeType != 'Polyline':
        raise ValueError(u"输入必须是线要素类，当前是: %s" % desc.shapeType)
    sr = desc.spatialReference

    geoms = []
    with arcpy.da.SearchCursor(in_polylines, ['SHAPE@']) as cursor:
        for row in cursor:
            geom = row[0]
            rings = []
            for part in geom:
                arr = arcpy.Array([arcpy.Point(p.X, p.Y) for p in part if p])
                if arr.count >= 3:
                    rings.append(arr)
            if rings:
                geoms.append(arcpy.Polygon(arcpy.Array(rings), sr))

    if not geoms:
        raise ValueError(u"没有可转换的线要素")

    arcpy.CopyFeatures_management(geoms, out_polygon)
    arcpy.RepairGeometry_management(out_polygon)
    print(u"输出面要素类: %s（%d 个）" % (out_polygon, len(geoms)))
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
