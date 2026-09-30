# -*- coding: utf-8 -*-
"""
用切割线切分要素 —— ArcMap 版

用一条（或多条）切割线把面/线要素切开，输出切割后的所有碎片，原属性复制到每块。用于按规划界线、道路中心线、河流界线切分地块/图斑，比手工裁剪快且不丢属性。

参数顺序（按地理处理工具原定义）：
  1. 输入面或线要素（被切的）
  2. 切割线要素（可多条）
  3. 输出切分结果

用法：
    python run.py <输入面或线要素（被切的）> <切割线要素（可多条）> <输出切分结果>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import math
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

def _attr_fields(fc):
    """非 OID/Geometry/Shape 系统字段名列表（保持原顺序）。"""
    return [f.name for f in arcpy.ListFields(fc)
            if f.type not in (u'OID', u'Geometry')
            and f.name.lower() not in (u'shape_length', u'shape_area')]

def _lengthen(line_geom, sr, factor=3.0):
    """把切割线两端延长，保证横贯目标要素。"""
    try:
        p0 = line_geom.firstPoint
        p1 = line_geom.lastPoint
        dx = (p1.X - p0.X) * (factor - 1.0) / 2.0
        dy = (p1.Y - p0.Y) * (factor - 1.0) / 2.0
        a = arcpy.Point(p0.X - dx, p0.Y - dy)
        b = arcpy.Point(p1.X + dx, p1.Y + dy)
        return arcpy.Polyline(arcpy.Array([a, b]), sr)
    except Exception:
        return line_geom




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
        print(u"用法: python run.py <输入面或线要素（被切的）> <切割线要素（可多条）> <输出切分结果>")
        return 1
    in_fc = argv[0]
    cut_line_fc = argv[1]
    out_fc = argv[2]
    arcpy.env.overwriteOutput = True
    st = arcpy.Describe(in_fc).shapeType
    if st not in (u'Polygon', u'Polyline'):
        raise ValueError(u"只支持面或线要素，输入是 %s" % st)
    sr = arcpy.Describe(in_fc).spatialReference

    cutters = []
    with arcpy.da.SearchCursor(cut_line_fc, ["SHAPE@"]) as cur:
        for (g,) in cur:
            if g is not None and g.length > 0:
                cutters.append(_lengthen(g, sr))

    out_dir, out_name = os.path.split(out_fc)
    if not out_dir:
        out_dir = arcpy.env.workspace
    arcpy.CreateFeatureclass_management(out_dir, out_name, st,
                                        in_fc, "", "", sr)
    in_fields = _attr_fields(in_fc)
    out_fields = _attr_fields(out_fc)

    n_in = int(arcpy.GetCount_management(in_fc).getOutput(0))
    n_out = 0
    n_cut = 0
    with arcpy.da.InsertCursor(out_fc, ["SHAPE@"] + out_fields) as ic:
        with arcpy.da.SearchCursor(in_fc, ["SHAPE@"] + in_fields) as sc:
            for row in sc:
                g = row[0]
                attrs = list(row[1:])
                if g is None:
                    continue
                pieces = [g]
                did = False
                for c in cutters:
                    newp = []
                    hit = False
                    for p in pieces:
                        try:
                            res = p.cut(c)
                        except Exception:
                            res = None
                        if res and len(res) >= 2 and any(
                                x is not None and x.length > 0 for x in res):
                            parts = [x for x in res
                                     if x is not None and x.length > 0]
                            newp.extend(parts)
                            hit = True
                        else:
                            newp.append(p)
                    if hit:
                        did = True
                    pieces = newp
                if did:
                    n_cut += 1
                for p in pieces:
                    ic.insertRow([p] + attrs)
                    n_out += 1
    print(u"切分 -> %s（%d 个要素 -> %d 块，被切过的 %d 个）"
          % (out_fc, n_in, n_out, n_cut))
    if n_out == n_in:
        print(u"提示: 没有要素被切开，检查切割线是否横贯目标要素")
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
