# -*- coding: utf-8 -*-
"""
DEM 河谷趋势面剥离（去趋势） —— ArcMap 版

用河谷中心线的高程做 IDW 插值得到「河谷纵向趋势面」，再做圆形邻域平滑，最后从 DEM 里减掉趋势面，得到**去趋势 DEM**（相对河谷底面的高度）。用于剥离河道整体纵坡，突出河床与滩地的局部起伏，是水面范围提取的前置步骤。

参数顺序（按地理处理工具原定义）：
  1. 输入 DEM 栅格
  2. 河谷中心线（河流线）
  3. 趋势面圆形平滑半径（像元数，一般 30~50）
  4. 输出去趋势 DEM 栅格

用法：
    python run.py <输入 DEM 栅格> <河谷中心线（河流线）> <趋势面圆形平滑半径（像元数，一般 30~50）> <输出去趋势 DEM 栅格>
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
        print(u"用法: python run.py <输入 DEM 栅格> <河谷中心线（河流线）> <趋势面圆形平滑半径（像元数，一般 30~50）> <输出去趋势 DEM 栅格>")
        return 1
    dem = argv[0]
    flowline = argv[1]
    smooth_cells = int(float(argv[2]))
    out_raster = argv[3]
    if arcpy.CheckExtension('spatial') != 'Available':
        raise RuntimeError(u"需要 Spatial Analyst 扩展许可")
    arcpy.CheckOutExtension('spatial')
    try:
        arcpy.env.overwriteOutput = True
        if smooth_cells < 1:
            raise ValueError(u"平滑半径至少 1 个像元")
        ras = arcpy.Raster(dem)
        cell = float(ras.meanCellWidth)
        x0 = float(ras.extent.XMin)
        y1 = float(ras.extent.YMax)
        dem_arr = arcpy.RasterToNumPyArray(dem)
        try:
            nd = float(ras.noDataValue)
        except Exception:
            nd = None
        sgdb = arcpy.env.scratchGDB

        # 河流线折点 + DEM 采样高程
        pts = r'in_memory\fl_pts'
        arcpy.FeatureVerticesToPoints_management(flowline, pts, "ALL")
        pt_fc = os.path.join(sgdb, u'dtrd_pts')
        arcpy.CopyFeatures_management(pts, pt_fc)
        arcpy.AddField_management(pt_fc, "Z", "DOUBLE")
        with arcpy.da.UpdateCursor(pt_fc, ["SHAPE@XY", "Z"]) as cur:
            for row in cur:
                xy = row[0]
                if xy is None:
                    continue
                c = int((xy[0] - x0) / cell)
                r = int((y1 - xy[1]) / cell)
                if 0 <= r < dem_arr.shape[0] and 0 <= c < dem_arr.shape[1]:
                    v = float(dem_arr[r, c])
                    if nd is not None and v == nd:
                        cur.deleteRow()
                        continue
                    row[1] = v
                    cur.updateRow(row)
        n_pts = int(arcpy.GetCount_management(pt_fc).getOutput(0))
        if n_pts < 3:
            raise RuntimeError(u"河流线折点太少（%d 个），先加密折点再跑" % n_pts)
        print(u"  河流线采样点 %d 个" % n_pts)

        # IDW 趋势面 + 平滑 + 相减
        # 河流线折点常共线，IDW 默认输出范围高度为 0 会报 010092，
        # 必须显式把输出范围钉到 DEM 范围
        arcpy.env.extent = ras.extent
        trend = arcpy.sa.Idw(pt_fc, "Z", cell, 2)
        trend_s = arcpy.sa.FocalStatistics(
            trend, arcpy.sa.NbrCircle(int(smooth_cells), "CELL"), "MEAN")
        detrend = arcpy.sa.Minus(dem, trend_s)
        detrend.save(out_raster)
        try:
            arcpy.CalculateStatistics_management(out_raster)
        except Exception:
            pass
        arcpy.Delete_management(pt_fc)
        print(u"去趋势 DEM -> %s（平滑半径 %d 像元）"
              % (out_raster, smooth_cells))
        print(u"提示: 用 hydro-water-surface-extent 按高度阈值圈水面范围")
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
