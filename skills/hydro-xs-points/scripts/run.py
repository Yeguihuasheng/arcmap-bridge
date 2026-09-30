# -*- coding: utf-8 -*-
"""
横断面线生成测点（带高程采样） —— ArcMap 版

把每条横断面线按指定间距加密成测点，输出带断面编号、距左岸起点距离、平面坐标的测点要素；给 DEM 时每个测点自动采样高程写进 Z 字段。用于河床断面测量布点、断面形态与冲淤分析的基础数据。

参数顺序（按地理处理工具原定义）：
  1. 输入横断面线要素
  2. 断面编号字段（每个断面唯一，如 Seq/断面号）
  3. 测点间距（线坐标系单位，如米）
  4. DEM 栅格（可选，填 # 不采高程）
  5. 输出测点要素

用法：
    python run.py <输入横断面线要素> <断面编号字段（每个断面唯一，如 Seq/断面号）> <测点间距（线坐标系单位，如米）> <DEM 栅格（可选，填 # 不采高程）> <输出测点要素>
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
    if len(argv) < 5:
        print(u"用法: python run.py <输入横断面线要素> <断面编号字段（每个断面唯一，如 Seq/断面号）> <测点间距（线坐标系单位，如米）> <DEM 栅格（可选，填 # 不采高程）> <输出测点要素>")
        return 1
    cross_section = argv[0]
    seq_field = argv[1]
    station_dist = float(argv[2])
    dem = argv[3]
    out_fc = argv[4]
    arcpy.env.overwriteOutput = True
    if not _has_field(cross_section, seq_field):
        raise ValueError(u"断面线里没有编号字段: %s" % seq_field)
    if station_dist <= 0:
        raise ValueError(u"测点间距必须大于 0")
    sr = arcpy.Describe(cross_section).spatialReference

    use_dem = (dem or u'').strip()
    if use_dem == u'#':
        use_dem = u''
    arr = None
    nd = None
    cell = None
    x0 = y1 = None
    if use_dem:
        ras = arcpy.Raster(use_dem)
        cell = float(ras.meanCellWidth)
        x0 = float(ras.extent.XMin)
        y1 = float(ras.extent.YMax)
        arr = arcpy.RasterToNumPyArray(use_dem)
        try:
            nd = float(ras.noDataValue)
        except Exception:
            nd = None

    def _z(px, py):
        if arr is None:
            return None
        c = int((px - x0) / cell)
        r = int((y1 - py) / cell)
        if r < 0 or r >= arr.shape[0] or c < 0 or c >= arr.shape[1]:
            return None
        v = float(arr[r, c])
        if nd is not None and v == nd:
            return None
        return v

    out_dir, out_name = os.path.split(out_fc)
    if not out_dir:
        out_dir = arcpy.env.workspace
    arcpy.CreateFeatureclass_management(out_dir, out_name, "POINT",
                                        "", "", "", sr)
    arcpy.AddField_management(out_fc, "SEQ", "TEXT", "", "", 50)
    arcpy.AddField_management(out_fc, "DIST", "DOUBLE")
    arcpy.AddField_management(out_fc, "POINT_X", "DOUBLE")
    arcpy.AddField_management(out_fc, "POINT_Y", "DOUBLE")
    arcpy.AddField_management(out_fc, "POINT_Z", "DOUBLE")

    n_line = 0
    n_pt = 0
    with arcpy.da.InsertCursor(out_fc, ["SHAPE@", "SEQ", "DIST",
                                        "POINT_X", "POINT_Y",
                                        "POINT_Z"]) as ic:
        with arcpy.da.SearchCursor(cross_section,
                                   ["SHAPE@", seq_field]) as sc:
            for g, seq in sc:
                if g is None or g.length <= 0:
                    continue
                n_line += 1
                L = g.length
                d = 0.0
                while True:
                    pt = g.positionAlongLine(min(d, L), False).firstPoint
                    z = _z(pt.X, pt.Y)
                    ic.insertRow([arcpy.PointGeometry(pt, sr), _u(seq),
                                  round(min(d, L), 4), pt.X, pt.Y, z])
                    n_pt += 1
                    if d >= L:
                        break
                    d += station_dist
    print(u"测点 -> %s（%d 条断面共 %d 个点，间距 %g）"
          % (out_fc, n_line, n_pt, station_dist))
    if use_dem:
        print(u"高程已按 DEM 采样（NoData 处 Z 为空）")
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
