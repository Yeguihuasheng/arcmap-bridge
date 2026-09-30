# -*- coding: utf-8 -*-
"""
按时刻算太阳位置并生成山体阴影 —— ArcMap 版

给定分析区域、DEM 和某个具体时刻（日期+时间+时区），先算出该时刻的太阳方位角与高度角，再按这个角度生成山体阴影栅格。可用于建筑日照间距校核、光伏选址的遮挡判断、地形晕渲图出图。太阳在地平线以下时输出常量 0 栅格。

参数顺序（按地理处理工具原定义）：
  1. 分析区域面要素（取中心点当观测位置，并作为处理范围）
  2. 输入高程栅格 DEM
  3. 日期时间，格式 YYYY-MM-DD HH:MM（本地时间）
  4. 时区偏移小时数（东八区填 8，西五区填 -5）
  5. 输出山体阴影栅格

用法：
    python run.py <分析区域面要素（取中心点当观测位置，并作为处理范围）> <输入高程栅格 DEM> <日期时间，格式 YYYY-MM-DD HH:MM（本地时间）> <时区偏移小时数（东八区填 8，西五区填 -5）> <输出山体阴影栅格>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import math
import datetime
import arcpy


def parse_dt(text):
    """宽松解析日期时间：YYYY-MM-DD HH:MM 为主，兼容几种常见写法。"""
    t = (text or u'').strip()
    fmts = (u"%Y-%m-%d %H:%M", u"%Y-%m-%d %H:%M:%S", u"%Y/%m/%d %H:%M",
            u"%Y/%m/%d %H:%M:%S", u"%Y-%m-%d", u"%Y/%m/%d",
            u"%m/%d/%Y %I:%M:%S %p", u"%m/%d/%Y %H:%M")
    for f in fmts:
        try:
            return datetime.datetime.strptime(t, f)
        except ValueError:
            continue
    raise ValueError(u"日期时间无法识别，请用 YYYY-MM-DD HH:MM，例如 2026-06-21 12:00")


def julian_day(d):
    a = (14 - d.month) // 12
    y = d.year + 4800 - a
    m = d.month + 12 * a - 3
    return d.day + ((153 * m + 2) // 5) + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def center_lonlat(aoi):
    """取分析区域的中心点，投影到 WGS84 经纬度后返回 (经度, 纬度)。"""
    tmp = r'in_memory\aoi_center'
    arcpy.FeatureToPoint_management(aoi, tmp, "CENTROID")
    sr_wgs = arcpy.SpatialReference()
    sr_wgs.factoryCode = 4326
    sr_wgs.create()
    # 用 SHAPE@XY 取中心点坐标，游标传 spatial_reference 会自动投影到 WGS84
    with arcpy.da.SearchCursor(tmp, ["SHAPE@XY"], None, sr_wgs) as cur:
        for row in cur:
            xy = row[0]
            if xy is None:
                break
            return (float(xy[0]), float(xy[1]))
    raise RuntimeError(u"取不到分析区域的中心点，请检查输入面要素是否为空")


def sun_position(utc_dt, lon, lat):
    """按简化天文算法算太阳位置，返回 (方位角, 高度角)，单位度。

    方位角以正北为 0 顺时针递增，正好是 arcpy.sa.Hillshade 需要的角度。
    """
    two_pi = math.pi * 2
    tt = utc_dt.timetuple()
    temp_hour = tt.tm_hour + tt.tm_min / 60.0 + tt.tm_sec / 3600.0
    tm = julian_day(utc_dt) - 2451545.0

    mnlong = (280.460 + 0.9856474 * tm) % 360
    mnanom = math.radians((357.528 + 0.9856003 * tm) % 360)
    eclong = (mnlong + 1.915 * math.sin(mnanom) + 0.020 * math.sin(2 * mnanom)) % 360
    oblqec = 23.439 - 0.0000004 * tm
    eclong_r = math.radians(eclong)
    oblqec_r = math.radians(oblqec)

    num = math.cos(oblqec_r) * math.sin(eclong_r)
    den = math.cos(eclong_r)
    ra = math.atan(num / den)
    if den < 0:
        ra += math.pi
    if den >= 0 and num < 0:
        ra += two_pi
    dec = math.asin(math.sin(oblqec_r) * math.sin(eclong_r))

    gmst = (6.697375 + 0.0657098242 * tm + temp_hour) % 24
    lmst = math.radians(((gmst + lon / 15.0) % 24) * 15.0)
    ha = lmst - ra
    if ha < -math.pi:
        ha += two_pi
    if ha > math.pi:
        ha -= two_pi

    lat_r = math.radians(lat)
    cos_zen = math.sin(lat_r) * math.sin(dec) + math.cos(lat_r) * math.cos(dec) * math.cos(ha)
    cos_zen = max(-1.0, min(1.0, cos_zen))
    zen = math.acos(cos_zen)

    el = math.asin(max(-1.0, min(1.0,
        math.sin(dec) * math.sin(lat_r) + math.cos(dec) * math.cos(lat_r) * math.cos(ha))))
    denom = math.cos(lat_r) * math.sin(zen)
    if abs(denom) < 1e-12:
        az = 0.0
    else:
        az = math.acos(max(-1.0, min(1.0,
            ((math.sin(lat_r) * math.cos(zen)) - math.sin(dec)) / denom)))

    el = math.degrees(el)
    az = math.degrees(az)
    if ha > 0:
        az = az + 180
    else:
        az = 540 - az
    return (az % 360, el)




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
        print(u"用法: python run.py <分析区域面要素（取中心点当观测位置，并作为处理范围）> <输入高程栅格 DEM> <日期时间，格式 YYYY-MM-DD HH:MM（本地时间）> <时区偏移小时数（东八区填 8，西五区填 -5）> <输出山体阴影栅格>")
        return 1
    aoi = argv[0]
    dem = argv[1]
    date_time = argv[2]
    tz_offset = float(argv[3])
    out_hs = argv[4]
    if arcpy.CheckExtension('spatial') != 'Available':
        raise RuntimeError(u"需要 Spatial Analyst 扩展许可")
    arcpy.CheckOutExtension('spatial')
    try:
        arcpy.env.overwriteOutput = True
        local_dt = parse_dt(date_time)
        utc_dt = local_dt - datetime.timedelta(hours=tz_offset)
        lon, lat = center_lonlat(aoi)
        az, alt = sun_position(utc_dt, lon, lat)
        print(u"观测点经纬度: %.6f, %.6f" % (lon, lat))
        print(u"当地时间: %s（UTC%+g）" % (local_dt.strftime(u"%Y-%m-%d %H:%M"), tz_offset))
        print(u"太阳方位角: %.2f 度，高度角: %.2f 度" % (az, alt))

        arcpy.env.extent = aoi
        arcpy.env.mask = aoi
        arcpy.env.cellSize = dem
        arcpy.env.snapRaster = dem
        if alt <= 0:
            print(u"太阳在地平线以下（夜间），输出常量 0 栅格")
            arcpy.sa.CreateConstantRaster(0, "INTEGER").save(out_hs)
        else:
            arcpy.sa.Hillshade(dem, az, alt, "NO_SHADOWS").save(out_hs)
        arcpy.CalculateStatistics_management(out_hs)
        print(u"山体阴影 -> %s" % out_hs)
        print(u"提示: 想看不同季节/时刻的对比，改 date_time 再跑一次")
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
