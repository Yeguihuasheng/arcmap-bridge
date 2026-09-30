# -*- coding: utf-8 -*-
"""
从线/面要素提取点（顶点/端点/中点/质心） —— ArcMap 版

把线或面要素转换成点要素，可选 7 种取点方式：全部折点、起点、终点、首末两点、中点、质心（重心）、真质心（面积质心）。属性全部保留。用于批量生成标注点、界桩点、断面桩点、把面转点做后续分析。

参数顺序（按地理处理工具原定义）：
  1. 输入线或面要素
  2. 输出点要素
  3. 取点方式：ALL/START/END/MID/BOTH_ENDS/CENTROID/TRUE_CENTROID

用法：
    python run.py <输入线或面要素> <输出点要素> <取点方式：ALL/START/END/MID/BOTH_ENDS/CENTROID/TRUE_CENTROID>
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

def _attr_fields(fc):
    """非 OID/Geometry/Shape 系统字段名列表（保持原顺序）。"""
    return [f.name for f in arcpy.ListFields(fc)
            if f.type not in (u'OID', u'Geometry')
            and f.name.lower() not in (u'shape_length', u'shape_area')]




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
        print(u"用法: python run.py <输入线或面要素> <输出点要素> <取点方式：ALL/START/END/MID/BOTH_ENDS/CENTROID/TRUE_CENTROID>")
        return 1
    in_fc = argv[0]
    out_pt_fc = argv[1]
    point_type = argv[2]
    arcpy.env.overwriteOutput = True
    pt = (point_type or u'').strip().upper()
    valid = (u"ALL", u"START", u"END", u"MID", u"BOTH_ENDS",
             u"CENTROID", u"TRUE_CENTROID")
    if pt not in valid:
        raise ValueError(u"取点方式只能是 %s 之一，实际: %s"
                         % (u'/'.join(valid), point_type))

    if pt in (u"ALL", u"START", u"END", u"MID", u"BOTH_ENDS"):
        arcpy.FeatureVerticesToPoints_management(in_fc, out_pt_fc, pt)
        cnt = arcpy.GetCount_management(out_pt_fc).getOutput(0)
        print(u"取点(%s) -> %s（%s 个点）" % (pt, out_pt_fc, cnt))
        return 0

    sr = arcpy.Describe(in_fc).spatialReference
    out_dir, out_name = os.path.split(out_pt_fc)
    if not out_dir:
        out_dir = arcpy.env.workspace
    arcpy.CreateFeatureclass_management(out_dir, out_name, "POINT",
                                        in_fc, "", "", sr)
    in_fields = _attr_fields(in_fc)
    out_fields = _attr_fields(out_pt_fc)
    made = 0
    with arcpy.da.InsertCursor(out_pt_fc, ["SHAPE@"] + out_fields) as ic:
        with arcpy.da.SearchCursor(in_fc, ["SHAPE@"] + in_fields) as sc:
            for row in sc:
                g = row[0]
                if g is None:
                    continue
                c = g.trueCentroid if pt == u"TRUE_CENTROID" else g.centroid
                if c is None:
                    continue
                ic.insertRow([arcpy.PointGeometry(
                    arcpy.Point(c.X, c.Y), sr)] + list(row[1:]))
                made += 1
    print(u"取点(%s) -> %s（%d 个点）" % (pt, out_pt_fc, made))
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
