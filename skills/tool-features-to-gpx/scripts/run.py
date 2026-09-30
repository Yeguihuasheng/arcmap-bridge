# -*- coding: utf-8 -*-
"""
要素导出 GPX —— ArcMap 版

把点或线要素导出为 GPX 1.1 文件：点转 waypoint（wpt）、线转 track（trk），可指定名称与描述字段。导出后可直接拷给手持 GPS、两步路、户外助手、Google Earth 使用。

参数顺序（按地理处理工具原定义）：
  1. 输入点或线要素
  2. 名称字段（GPX 里的 name；填 # 用要素 OID）
  3. 描述字段（GPX 里的 desc；填 # 留空）
  4. 输出 GPX 文件路径（.gpx）

用法：
    python run.py <输入点或线要素> <名称字段（GPX 里的 name；填 # 用要素 OID）> <描述字段（GPX 里的 desc；填 # 留空）> <输出 GPX 文件路径（.gpx）>
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

def _xml_escape(s):
    return (_u(s).replace(u'&', u'&amp;').replace(u'<', u'&lt;')
            .replace(u'>', u'&gt;').replace(u'"', u'&quot;'))




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
        print(u"用法: python run.py <输入点或线要素> <名称字段（GPX 里的 name；填 # 用要素 OID）> <描述字段（GPX 里的 desc；填 # 留空）> <输出 GPX 文件路径（.gpx）>")
        return 1
    in_fc = argv[0]
    name_field = argv[1]
    desc_field = argv[2]
    out_gpx = argv[3]
    arcpy.env.overwriteOutput = True
    st = arcpy.Describe(in_fc).shapeType
    if st not in (u'Point', u'Multipoint', u'Polyline'):
        raise ValueError(u"只支持点或线要素，输入是 %s" % st)

    sr4326 = arcpy.SpatialReference()
    sr4326.factoryCode = 4326
    sr4326.create()

    nf = (name_field or u'').strip()
    if nf == u'#' or not nf:
        nf = None
    df = (desc_field or u'').strip()
    if df == u'#' or not df:
        df = None
    if nf and not _has_field(in_fc, nf):
        raise ValueError(u"输入里没有名称字段: %s" % nf)
    if df and not _has_field(in_fc, df):
        raise ValueError(u"输入里没有描述字段: %s" % df)

    cols = [u'SHAPE@', u'OID@'] + ([nf] if nf else []) + ([df] if df else [])
    items = []
    with arcpy.da.SearchCursor(in_fc, cols, None, sr4326) as cur:
        for row in cur:
            g, oid = row[0], row[1]
            nm = _u(row[2]) if nf else u'P%d' % oid
            ds = _u(row[3]) if df else u''
            if g is None:
                continue
            items.append((g, nm, ds))

    lines = [u'<?xml version="1.0" encoding="UTF-8"?>',
             u'<gpx version="1.1" creator="arcmap-bridge skills" '
             u'xmlns="http://www.topografix.com/GPX/1/1">']

    def _pt_xml(tag, x, y, z, nm, ds):
        s = u'<%s lat="%.8f" lon="%.8f">' % (tag, y, x)
        if z is not None:
            s += u'<ele>%.2f</ele>' % z
        s += u'<name>%s</name>' % _xml_escape(nm)
        if ds:
            s += u'<desc>%s</desc>' % _xml_escape(ds)
        return s + u'</%s>' % tag

    n_wpt = 0
    n_trk = 0
    for g, nm, ds in items:
        if st in (u'Point', u'Multipoint'):
            if st == u'Point':
                plist = [g]
            else:
                plist = []
                try:
                    for i in range(g.pointCount):
                        plist.append(g.getPart(i))
                except Exception:
                    plist = [g]
            for pg in plist:
                pt = pg.firstPoint if hasattr(pg, u'firstPoint') else pg
                if pt is None:
                    continue
                z = None
                if getattr(pt, u'Z', None) is not None:
                    try:
                        if not (pt.Z != pt.Z):  # NaN 判定
                            z = float(pt.Z)
                    except Exception:
                        z = None
                lines.append(_pt_xml(u'wpt', pt.X, pt.Y, z, nm, ds))
                n_wpt += 1
        else:
            lines.append(u'<trk><name>%s</name>' % _xml_escape(nm))
            if ds:
                lines.append(u'<desc>%s</desc>' % _xml_escape(ds))
            for i in range(g.partCount):
                arr = g.getPart(i)
                lines.append(u'<trkseg>')
                for j in range(arr.count):
                    p = arr.getObject(j)
                    if p is None:
                        continue
                    z = None
                    if getattr(p, u'Z', None) is not None:
                        try:
                            if not (p.Z != p.Z):
                                z = float(p.Z)
                        except Exception:
                            z = None
                    lines.append(_pt_xml(u'trkpt', p.X, p.Y, z, u'', u''))
                lines.append(u'</trkseg>')
            lines.append(u'</trk>')
            n_trk += 1

    lines.append(u'</gpx>')
    with open(out_gpx, 'wb') as fh:
        fh.write(u'\n'.join(lines).encode(u'utf-8'))
    print(u"GPX -> %s（航点 %d 个，轨迹 %d 条）" % (out_gpx, n_wpt, n_trk))
    if not n_wpt and not n_trk:
        raise RuntimeError(u"没有导出任何要素，请检查输入是否为空")
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
