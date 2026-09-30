# -*- coding: utf-8 -*-
"""
填补面内空洞 —— ArcMap 版

把面要素内部的孔洞（内环）填实，输出无孔的实心面，多部件面的每个外环各自保留。用于消除图斑中被误挖的空白、制图前把带洞的行政区/地类面变成实心便于标注。

参数顺序（按地理处理工具原定义）：
  1. 输入面要素（可带内环空洞）
  2. 输出实心面要素

用法：
    python run.py <输入面要素（可带内环空洞）> <输出实心面要素>
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
    return [p.strip() for p in t.split(u';') if p.strip()]


def _has_field(ds, name):
    for f in arcpy.ListFields(ds):
        if f.name.upper() == name.upper():
            return True
    return False

def _ring_area(arr):
    """ Shoelace 带符号面积；正负代表环的方向。"""
    pts = [arr.getObject(i) for i in range(arr.count)]
    if len(pts) < 3:
        return 0.0
    s = 0.0
    n = len(pts)
    for i in range(n):
        x1 = pts[i].X
        y1 = pts[i].Y
        x2 = pts[(i + 1) % n].X
        y2 = pts[(i + 1) % n].Y
        s += x1 * y2 - x2 * y1
    return s / 2.0


def _split_rings(geom):
    """把几何拆成独立环列表：每个 part 的 Array 里外环与内环之间用 None 点分隔。"""
    rings = []
    for i in range(geom.partCount):
        arr = geom.getPart(i)
        cur = arcpy.Array()
        for j in range(arr.count):
            p = arr.getObject(j)
            if p is None:
                if cur.count >= 3:
                    rings.append(cur)
                cur = arcpy.Array()
            else:
                cur.add(arcpy.Point(p.X, p.Y))
        if cur.count >= 3:
            rings.append(cur)
    return rings




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
        print(u"用法: python run.py <输入面要素（可带内环空洞）> <输出实心面要素>")
        return 1
    in_poly_fc = argv[0]
    out_poly_fc = argv[1]
    arcpy.env.overwriteOutput = True
    sr = arcpy.Describe(in_poly_fc).spatialReference
    arcpy.CopyFeatures_management(in_poly_fc, out_poly_fc)

    filled = 0
    untouched = 0
    with arcpy.da.UpdateCursor(out_poly_fc, ["SHAPE@"]) as cur:
        for (geom,) in cur:
            if geom is None:
                untouched += 1
                continue
            rings = _split_rings(geom)
            if len(rings) <= 1:
                untouched += 1
                continue
            areas = [_ring_area(r) for r in rings]
            base = 0
            for i in range(1, len(areas)):
                if abs(areas[i]) > abs(areas[base]):
                    base = i
            keep = [r for r, a in zip(rings, areas)
                    if (a >= 0) == (areas[base] >= 0)]
            if len(keep) == len(rings) or not keep:
                untouched += 1
                continue
            arr = arcpy.Array()
            for r in keep:
                arr.add(r)
            cur.updateRow([arcpy.Polygon(arr, sr)])
            filled += 1
    print(u"填洞 -> %s（填实 %d 个面，%d 个面本就无洞原样通过）"
          % (out_poly_fc, filled, untouched))
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
