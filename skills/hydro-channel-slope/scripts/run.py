# -*- coding: utf-8 -*-
"""
河道范围内坡度栅格 —— ArcMap 版

对 DEM 计算坡度（可设 z 因子校正高程单位），再用河道面裁出河道范围内的坡度栅格。用于河道比降分析、护岸稳定性评价、水力计算的坡度输入。

参数顺序（按地理处理工具原定义）：
  1. 输入 DEM 栅格
  2. 河道面要素（裁剪范围）
  3. z 因子（水平单位是米、高程也是米时填 1）
  4. 输出河道坡度栅格

用法：
    python run.py <输入 DEM 栅格> <河道面要素（裁剪范围）> <z 因子（水平单位是米、高程也是米时填 1）> <输出河道坡度栅格>
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
        print(u"用法: python run.py <输入 DEM 栅格> <河道面要素（裁剪范围）> <z 因子（水平单位是米、高程也是米时填 1）> <输出河道坡度栅格>")
        return 1
    dem = argv[0]
    banks_poly = argv[1]
    z_factor = float(argv[2])
    out_raster = argv[3]
    if arcpy.CheckExtension('spatial') != 'Available':
        raise RuntimeError(u"需要 Spatial Analyst 扩展许可")
    arcpy.CheckOutExtension('spatial')
    try:
        arcpy.env.overwriteOutput = True
        if z_factor <= 0:
            raise ValueError(u"z 因子必须大于 0")
        slope = arcpy.sa.Slope(dem, "DEGREE", z_factor)
        out = arcpy.sa.ExtractByMask(slope, banks_poly)
        out.save(out_raster)
        try:
            arcpy.CalculateStatistics_management(out_raster)
        except Exception:
            pass
        print(u"河道坡度 -> %s（单位：度）" % out_raster)
        print(u"提示: 要河段平均比降可用分区统计（ZonalStatistics）对河道分段取均值")
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
