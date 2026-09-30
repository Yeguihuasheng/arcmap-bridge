# -*- coding: utf-8 -*-
"""
点按分组顺序连成面 —— ArcMap 版

把点要素按「分组字段 + 排序字段」的先后顺序依次连接闭合生成面要素，每组一个面。用于把实测边界点、界桩点、采样点串还原成地块面。输出面带分组值与点数两个字段。

参数顺序（按地理处理工具原定义）：
  1. 输入点要素
  2. 输出面要素
  3. 分组字段（每组连成一个面）
  4. 组内排序字段（决定连线顺序，如 顺序号/桩号）

用法：
    python run.py <输入点要素> <输出面要素> <分组字段（每组连成一个面）> <组内排序字段（决定连线顺序，如 顺序号/桩号）>
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

try:
    _NUM = (int, long, float)
except NameError:
    _NUM = (int, float)


def _sort_key(v):
    """数值按数值序，其余按文本序，避免 py2 里数值和字符串直接比较报错。"""
    if isinstance(v, _NUM) and not isinstance(v, bool):
        return (0, float(v), u'')
    return (1, 0.0, _u(v))




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
        print(u"用法: python run.py <输入点要素> <输出面要素> <分组字段（每组连成一个面）> <组内排序字段（决定连线顺序，如 顺序号/桩号）>")
        return 1
    in_pt_fc = argv[0]
    out_poly_fc = argv[1]
    group_field = argv[2]
    sort_field = argv[3]
    arcpy.env.overwriteOutput = True
    gf = (group_field or u'').strip()
    if gf == u'#' or not gf:
        gf = None
    sf = (sort_field or u'').strip()
    if sf == u'#':
        sf = None
    if gf and not _has_field(in_pt_fc, gf):
        raise ValueError(u"输入里没有分组字段: %s" % gf)
    if sf and not _has_field(in_pt_fc, sf):
        raise ValueError(u"输入里没有排序字段: %s" % sf)

    sr = arcpy.Describe(in_pt_fc).spatialReference
    cols = ["SHAPE@XY"] + ([gf] if gf else []) + ([sf] if sf else [])
    rows = []
    with arcpy.da.SearchCursor(in_pt_fc, cols) as cur:
        for r in cur:
            xy = r[0]
            gval = _u(r[1]) if gf else u'ALL'
            sval = r[2] if sf else 0
            if xy is None:
                continue
            rows.append((float(xy[0]), float(xy[1]), gval, sval))
    if not rows:
        raise RuntimeError(u"输入点要素里没有可用的点")
    rows.sort(key=lambda t: (_u(t[2]), _sort_key(t[3])))

    out_dir, out_name = os.path.split(out_poly_fc)
    if not out_dir:
        out_dir = arcpy.env.workspace
    arcpy.CreateFeatureclass_management(out_dir, out_name, "POLYGON",
                                        "", "", "", sr)
    arcpy.AddField_management(out_poly_fc, "GROUP_VAL", "TEXT", "", "", 254)
    arcpy.AddField_management(out_poly_fc, "PT_CNT", "LONG")

    groups = []
    for x, y, gval, _s in rows:
        if not groups or groups[-1][0] != gval:
            groups.append((gval, []))
        groups[-1][1].append((x, y))

    made = 0
    skipped = []
    with arcpy.da.InsertCursor(out_poly_fc,
                               ["SHAPE@", "GROUP_VAL", "PT_CNT"]) as ic:
        for gval, pts in groups:
            if len(pts) < 3:
                skipped.append(u'%s(%d点)' % (gval, len(pts)))
                continue
            arr = arcpy.Array()
            for x, y in pts:
                arr.add(arcpy.Point(x, y))
            arr.add(arcpy.Point(pts[0][0], pts[0][1]))
            ic.insertRow([arcpy.Polygon(arr, sr), gval, len(pts)])
            made += 1
    print(u"连面 -> %s（%d 组成面）" % (out_poly_fc, made))
    if skipped:
        print(u"跳过不足 3 点的组: %s" % u'、'.join(skipped))
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
