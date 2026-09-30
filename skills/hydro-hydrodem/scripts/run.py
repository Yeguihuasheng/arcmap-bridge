# -*- coding: utf-8 -*-
"""
把切线烧进 DEM（水文修正） —— ArcMap 版

沿切线（culvert/堤防开口线等）把 DEM 高程压到沿线最低值，打通被路堤、坝体挡住的水流路径，产出水文修正后的 DEM。是流域分析前「让水流的过去」的关键预处理。

参数顺序（按地理处理工具原定义）：
  1. 输出工作空间（GDB 路径）
  2. 切线要素类（在堤/坝/路埂开口处画的线）
  3. 输入 DEM 栅格
  4. 切线加宽像元数（0=不加宽，一般 1~3）

用法：
    python run.py <输出工作空间（GDB 路径）> <切线要素类（在堤/坝/路埂开口处画的线）> <输入 DEM 栅格> <切线加宽像元数（0=不加宽，一般 1~3）>
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
        print(u"用法: python run.py <输出工作空间（GDB 路径）> <切线要素类（在堤/坝/路埂开口处画的线）> <输入 DEM 栅格> <切线加宽像元数（0=不加宽，一般 1~3）>")
        return 1
    output_workspace = argv[0]
    cutlines = argv[1]
    dem = argv[2]
    widen_cells = int(float(argv[3]))
    if arcpy.CheckExtension(u'spatial') != u'Available':
        raise RuntimeError(u"需要 Spatial Analyst 扩展许可")
    arcpy.CheckOutExtension(u'spatial')
    try:
        arcpy.env.overwriteOutput = True
        if not arcpy.Exists(output_workspace):
            raise ValueError(u"输出工作空间不存在: %s" % output_workspace)
        cellsize = float(arcpy.GetRasterProperties_management(
            dem, u'CELLSIZEX').getOutput(0))
        arcpy.env.workspace = output_workspace
        arcpy.env.extent = dem
        arcpy.env.snapRaster = dem
        arcpy.env.cellSize = cellsize
        arcpy.env.compression = u'LZ77'
        arcpy.env.outputCoordinateSystem = dem

        oid_f = arcpy.Describe(cutlines).OIDFieldName
        oid_list = []
        with arcpy.da.SearchCursor(cutlines, [oid_f]) as cur:
            for row in cur:
                oid_list.append(row[0])
        if not oid_list:
            raise ValueError(u"切线要素类是空的")

        cut_ras = os.path.join(output_workspace, u'cutline_ras')
        arcpy.PolylineToRaster_conversion(cutlines, oid_f, cut_ras,
                                          u'MAXIMUM_LENGTH', u'NONE', cellsize)
        if widen_cells > 0:
            cut_ras = arcpy.sa.Expand(cut_ras, widen_cells, oid_list)
            print(u"  切线已加宽 %d 像元" % widen_cells)

        cut_min = arcpy.sa.ZonalStatistics(cut_ras, u'VALUE', dem, u'MINIMUM')
        dem_hydro = arcpy.sa.Con(arcpy.sa.IsNull(cut_min), dem, cut_min)
        out_path = os.path.join(output_workspace, u'dem_hydro')
        arcpy.CopyRaster_management(dem_hydro, out_path)
        arcpy.CalculateStatistics_management(out_path)
        arcpy.BuildPyramids_management(out_path)
        try:
            arcpy.Delete_management(cut_ras)
        except Exception:
            pass
        print(u"水文修正 DEM -> %s（烧入 %d 条切线）" % (out_path, len(oid_list)))
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
