# -*- coding: utf-8 -*-
"""
识别负地形洼地（带深度） —— ArcMap 版

用「填洼 − 原 DEM」找出负地形洼地：输出按面积范围过滤后的洼地多边形，并给每个洼地算出最大深度（最深点的下陷值）。典型用途是海底凹坑（pockmark）识别，也适用于陆上负地形（要求输入为全负值栅格，如海深）。

参数顺序（按地理处理工具原定义）：
  1. 输入负值栅格（海深/负地形 DEM，最大值必须 <= 0）
  2. 填洼 z 限制（超过该深度的洼地不填，0=不限制）
  3. 洼地最大面积（平方米，超过的丢弃）
  4. 输出洼地面要素

用法：
    python run.py <输入负值栅格（海深/负地形 DEM，最大值必须 <= 0）> <填洼 z 限制（超过该深度的洼地不填，0=不限制）> <洼地最大面积（平方米，超过的丢弃）> <输出洼地面要素>
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
        print(u"用法: python run.py <输入负值栅格（海深/负地形 DEM，最大值必须 <= 0）> <填洼 z 限制（超过该深度的洼地不填，0=不限制）> <洼地最大面积（平方米，超过的丢弃）> <输出洼地面要素>")
        return 1
    bathy = argv[0]
    z_limit = float(argv[1])
    max_area = float(argv[2])
    out_polygons = argv[3]
    if arcpy.CheckExtension(u'spatial') != u'Available':
        raise RuntimeError(u"需要 Spatial Analyst 扩展许可")
    arcpy.CheckOutExtension(u'spatial')
    try:
        arcpy.env.overwriteOutput = True
        ras = arcpy.Raster(bathy)
        if float(ras.maximum) > 0:
            raise ValueError(u"输入栅格必须全为负值（当前最大值 %s）"
                             % ras.maximum)

        # 填洼 -> 洼地 = 原值 - 填洼值（<=0，越负越深）
        if z_limit and z_limit > 0:
            fill = arcpy.sa.Fill(ras, z_limit)
        else:
            fill = arcpy.sa.Fill(ras)
        dep = arcpy.sa.Minus(ras, fill)
        dep_min = float(arcpy.GetRasterProperties_management(
            dep, u'MINIMUM').getOutput(0))
        if dep_min >= 0:
            raise RuntimeError(u"没找到任何洼地（填洼前后无差别）")
        remap = arcpy.sa.RemapRange([[dep_min, -0.000001, 1]])
        dep_rc = arcpy.sa.Reclassify(dep, u'VALUE', remap, u'NODATA')

        poly = r'in_memory\gdp_poly'
        arcpy.RasterToPolygon_conversion(dep_rc, poly, u'NO_SIMPLIFY',
                                         u'VALUE')
        # 面积过滤：下限 (3x像元)^2，上限 max_area
        cell = float(ras.meanCellWidth)
        min_area = (cell * 3) ** 2
        arcpy.AddField_management(poly, u'AREA_M', u'FLOAT')
        arcpy.CalculateField_management(poly, u'AREA_M',
                                        u'!SHAPE.area@SQUAREMETERS!',
                                        u'PYTHON_9.3')
        lyr = arcpy.MakeFeatureLayer_management(
            poly, u'gdp_lyr', u'AREA_M >= %s AND AREA_M <= %s'
            % (repr(min_area), repr(max_area)))
        cnt = int(arcpy.GetCount_management(lyr).getOutput(0))
        if cnt < 1:
            raise RuntimeError(
                u"面积范围 [%.0f, %.0f] 内没有洼地，请放宽 max_area"
                % (min_area, max_area))

        # 每个洼地的最大深度：分区取洼地栅格最小值，再空间挂接回面
        oid_f = arcpy.Describe(poly).OIDFieldName
        zonal = arcpy.sa.ZonalStatistics(lyr, oid_f, dep, u'MINIMUM',
                                         u'DATA')
        zp = r'in_memory\gdp_zp'
        arcpy.RasterToPoint_conversion(zonal, zp, u'VALUE')

        fms = arcpy.FieldMappings()
        fms.addTable(lyr)  # 先放目标全部字段（AREA_M 等），再加深度
        fm = arcpy.FieldMap()
        fm.addInputField(zp, u'GRID_CODE')
        of = fm.outputField
        of.name = u'POCK_DEP'
        of.aliasName = u'POCK_DEP'
        fm.outputField = of
        fm.mergeRule = u'MINIMUM'
        fms.addFieldMap(fm)
        joined = arcpy.SpatialJoin_analysis(lyr, zp, r'in_memory\gdp_join',
                                            u'JOIN_ONE_TO_ONE', u'KEEP_ALL',
                                            fms)
        arcpy.CopyFeatures_management(joined, out_polygons)
        for t in (poly, zp, joined, lyr):
            try:
                arcpy.Delete_management(t)
            except Exception:
                pass
        print(u"洼地 -> %s（%d 个，POCK_DEP=最大深度）" % (out_polygons, cnt))
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
