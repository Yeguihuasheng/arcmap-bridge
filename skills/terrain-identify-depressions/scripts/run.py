# -*- coding: utf-8 -*-
"""
识别地形洼地 —— ArcMap 版

用「填洼 — 与原高程相减」的方法在 DEM/水深栅格上识别洼地，按 z 限差与面积阈值过滤后输出洼地面要素类，可用于水库库容、内涝点、采坑排查。

参数顺序（按地理处理工具原定义）：
  1. 输入高程/水深栅格
  2. 填洼 z 限差（超过该深度不算洼地）
  3. 洼地最大面积（平方米）
  4. 输出洼地面要素类

用法：
    python run.py <输入高程/水深栅格> <填洼 z 限差（超过该深度不算洼地）> <洼地最大面积（平方米）> <输出洼地面要素类>
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
    if len(argv) < 4:
        print(u"用法: python run.py <输入高程/水深栅格> <填洼 z 限差（超过该深度不算洼地）> <洼地最大面积（平方米）> <输出洼地面要素类>")
        return 1
    in_raster = argv[0]
    z_limit = float(argv[1])
    max_area = float(argv[2])
    out_polygons = argv[3]
    arcpy.env.overwriteOutput = True
    if arcpy.CheckExtension('spatial') != 'Available':
        raise RuntimeError(u"需要 Spatial Analyst 扩展许可")
    arcpy.CheckOutExtension('spatial')
    try:
        bathy = arcpy.Raster(in_raster)
        fill_raster = arcpy.sa.Fill(bathy, z_limit)
        depression = arcpy.sa.Minus(bathy, fill_raster)

        minimum = float(arcpy.GetRasterProperties_management(
            depression, 'MINIMUM').getOutput(0))
        remap = arcpy.sa.RemapRange([[minimum, -1, 1]])
        reclass = arcpy.sa.Reclassify(depression, 'VALUE', remap, 'NODATA')
        polys = arcpy.RasterToPolygon_conversion(reclass, r'in_memory\dep',
                                                 'NO_SIMPLIFY', 'VALUE')

        cell = arcpy.Describe(bathy).meanCellWidth
        min_area = (cell * 3) ** 2
        arcpy.AddField_management(polys, 'AREA_M', 'FLOAT')
        arcpy.CalculateField_management(polys, 'AREA_M',
                                        '!SHAPE.area@SQUAREMETERS!', 'PYTHON')
        lyr = arcpy.MakeFeatureLayer_management(
            polys, 'dep_lyr', 'AREA_M >= %s AND AREA_M <= %s'
            % (min_area, max_area))
        arcpy.CopyFeatures_management(lyr, out_polygons)
        print(u"输出: %s，共 %s 个洼地"
              % (out_polygons, arcpy.GetCount_management(out_polygons).getOutput(0)))
        print(u"面积过滤区间: %.2f ~ %.2f 平方米" % (min_area, max_area))
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
