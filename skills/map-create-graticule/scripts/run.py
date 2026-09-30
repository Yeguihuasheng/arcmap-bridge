# -*- coding: utf-8 -*-
"""
生成经纬网（标准分幅格网） —— ArcMap 版

按给定范围与间隔（度）生成经纬网线：南北向经线 + 东西向纬线，每条线带方向类型与度分秒（DMS）标注字段。用于标准分幅图框、区位索引图、制图底图的坐标网。

参数顺序（按地理处理工具原定义）：
  1. 范围来源：图层路径，或 xmin ymin xmax ymax（WGS84 经纬度）
  2. 格网间隔（度，如 0.5 / 1 / 10）
  3. 输出格网线要素（WGS84）

用法：
    python run.py <范围来源：图层路径，或 xmin ymin xmax ymax（WGS84 经纬度）> <格网间隔（度，如 0.5 / 1 / 10）> <输出格网线要素（WGS84）>
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

def _dms(v, is_lat):
    hemi = (u'S' if v < 0 else u'N') if is_lat else (u'W' if v < 0 else u'E')
    a = abs(v)
    d = int(a)
    m = int((a - d) * 60)
    s = round((a - d - m / 60.0) * 3600, 2)
    if s >= 60:
        s = 0.0
        m += 1
    if m >= 60:
        m = 0
        d += 1
    return u'%d°%02d\'%05.2f"%s' % (d, m, s, hemi)




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
    if len(argv) < 3:
        print(u"用法: python run.py <范围来源：图层路径，或 xmin ymin xmax ymax（WGS84 经纬度）> <格网间隔（度，如 0.5 / 1 / 10）> <输出格网线要素（WGS84）>")
        return 1
    extent_src = argv[0]
    interval = float(argv[1])
    out_fc = argv[2]
    arcpy.env.overwriteOutput = True
    sr4326 = arcpy.SpatialReference()
    sr4326.factoryCode = 4326
    sr4326.create()

    src = (extent_src or u'').strip()
    if u' ' in src and not arcpy.Exists(src):
        parts = src.split()
        if len(parts) != 4:
            raise ValueError(u"范围要给 4 个数: xmin ymin xmax ymax")
        ext = arcpy.Extent(float(parts[0]), float(parts[1]),
                           float(parts[2]), float(parts[3]))
    else:
        if not arcpy.Exists(src):
            raise ValueError(u"范围图层不存在: %s" % src)
        d = arcpy.Describe(src)
        ext = d.extent.projectAs(sr4326) if d.spatialReference.name != sr4326.name else d.extent

    if interval <= 0 or interval > 30:
        raise ValueError(u"间隔须在 (0, 30] 度之间")
    xmin, ymin = ext.XMin, ext.YMin
    xmax, ymax = ext.XMax, ext.YMax
    if not (-180 <= xmin < xmax <= 180 and -90 <= ymin < ymax <= 90):
        raise ValueError(u"范围超出经纬度范围: %.4f %.4f %.4f %.4f"
                         % (xmin, ymin, xmax, ymax))

    out_dir, out_name = os.path.split(out_fc)
    if not out_dir:
        out_dir = arcpy.env.workspace
    arcpy.CreateFeatureclass_management(out_dir, out_name, "POLYLINE",
                                        "", "", "", sr4326)
    arcpy.AddField_management(out_fc, "LINE", "TEXT", "", "", 8)
    arcpy.AddField_management(out_fc, "DMS", "TEXT", "", "", 30)
    arcpy.AddField_management(out_fc, "DEG", "DOUBLE")

    lons = []
    v = int(xmin / interval) * interval
    while v <= xmax + 1e-9:
        if v >= xmin - 1e-9:
            lons.append(round(v, 6))
        v += interval
    lats = []
    v = int(ymin / interval) * interval
    while v <= ymax + 1e-9:
        if v >= ymin - 1e-9:
            lats.append(round(v, 6))
        v += interval
    if not lons or not lats:
        raise ValueError(u"范围太小放不下一根格网线")

    def _line(x1, y1, x2, y2):
        return arcpy.Polyline(arcpy.Array([arcpy.Point(x1, y1),
                                           arcpy.Point(x2, y2)]), sr4326)

    n = 0
    with arcpy.da.InsertCursor(out_fc, ["SHAPE@", "LINE", "DMS", "DEG"]) as ic:
        for lon in lons:
            ic.insertRow([_line(lon, ymin, lon, ymax), u'N-S',
                          _dms(lon, False), lon])
            n += 1
        for lat in lats:
            ic.insertRow([_line(xmin, lat, xmax, lat), u'E-W',
                          _dms(lat, True), lat])
            n += 1
    print(u"格网 -> %s（经线 %d 条 + 纬线 %d 条，间隔 %g 度）"
          % (out_fc, len(lons), len(lats), interval))
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
