# -*- coding: utf-8 -*-
"""
内侧缓冲带（面边界向内的环带） —— ArcMap 版

从面要素边界向内取指定宽度的一条环带（原面减去向内收缩后的内核，即贴着边界的那圈带状面）。用于道路面内侧绿化带、湖岸带、地块边缘 50 米管控带的快速提取。

参数顺序（按地理处理工具原定义）：
  1. 输入面要素
  2. 环带宽度（坐标系单位，如米）
  3. 输出内侧环带面要素

用法：
    python run.py <输入面要素> <环带宽度（坐标系单位，如米）> <输出内侧环带面要素>
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
        print(u"用法: python run.py <输入面要素> <环带宽度（坐标系单位，如米）> <输出内侧环带面要素>")
        return 1
    in_poly_fc = argv[0]
    buffer_dist = float(argv[1])
    out_poly_fc = argv[2]
    arcpy.env.overwriteOutput = True
    if buffer_dist <= 0:
        raise ValueError(u"内缩距离必须大于 0")
    d = arcpy.Describe(in_poly_fc)
    if d.spatialReference.type.lower() == u'geographic':
        print(u"警告: 输入是地理坐标系，距离单位是『度』，结果可能不是你要的")
    arcpy.CopyFeatures_management(in_poly_fc, out_poly_fc)

    shrunk = 0
    kept = 0
    with arcpy.da.UpdateCursor(out_poly_fc, ["SHAPE@"]) as cur:
        for (g,) in cur:
            if g is None:
                continue
            inner = g.buffer(-abs(buffer_dist))
            if inner is None or inner.area == 0:
                kept += 1
                continue
            cur.updateRow([g.difference(inner)])
            shrunk += 1
    print(u"内侧环带 -> %s（生成 %d 个，面太窄保留原样 %d 个）"
          % (out_poly_fc, shrunk, kept))
    if kept:
        print(u"提示: 有 %d 个面容不下该环带宽度，已按原图斑输出" % kept)
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
