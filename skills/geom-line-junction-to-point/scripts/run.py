# -*- coding: utf-8 -*-
"""
线交点转点（路网节点） —— ArcMap 版

求一批线要素之间的全部交点并生成点要素，可选按坐标去重。用于生成路网/管网节点、道路交叉口、河流交汇点，是网络构建与拓扑检查的前置步骤。

参数顺序（按地理处理工具原定义）：
  1. 输入线要素（自身内部也求交）
  2. 输出交点点要素
  3. 坐标去重（YES=相同位置只留一个；NO=全部保留；默认 YES）

用法：
    python run.py <输入线要素（自身内部也求交）> <输出交点点要素> <坐标去重（YES=相同位置只留一个；NO=全部保留；默认 YES）>
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
    if len(argv) < 3:
        print(u"用法: python run.py <输入线要素（自身内部也求交）> <输出交点点要素> <坐标去重（YES=相同位置只留一个；NO=全部保留；默认 YES）>")
        return 1
    in_line_fc = argv[0]
    out_pt_fc = argv[1]
    dedup = argv[2]
    arcpy.env.overwriteOutput = True
    st = arcpy.Describe(in_line_fc).shapeType
    if st != u'Polyline':
        raise ValueError(u"输入必须是线要素")
    dd = (dedup or u'YES').strip().upper()
    if dd not in (u'YES', u'NO'):
        raise ValueError(u"去重只能是 YES 或 NO")

    sr = arcpy.Describe(in_line_fc).spatialReference
    inter = r'in_memory\junc_raw'
    arcpy.Intersect_analysis([in_line_fc], inter, "NO_FID", "", "POINT")
    single = r'in_memory\junc_single'
    arcpy.MultipartToSinglepart_management(inter, single)

    pts = []
    with arcpy.da.SearchCursor(single, ["SHAPE@XY"]) as cur:
        for (xy,) in cur:
            if xy is not None:
                pts.append((float(xy[0]), float(xy[1])))

    if dd == u'YES':
        cnt = {}
        for x, y in pts:
            k = (round(x, 6), round(y, 6))
            cnt[k] = cnt.get(k, 0) + 1
        uniq = [(k[0], k[1], c) for k, c in cnt.items()]
    else:
        uniq = [(x, y, 1) for x, y in pts]

    out_dir, out_name = os.path.split(out_pt_fc)
    if not out_dir:
        out_dir = arcpy.env.workspace
    arcpy.CreateFeatureclass_management(out_dir, out_name, "POINT",
                                        "", "", "", sr)
    arcpy.AddField_management(out_pt_fc, "X", "DOUBLE")
    arcpy.AddField_management(out_pt_fc, "Y", "DOUBLE")
    arcpy.AddField_management(out_pt_fc, "CNT", "LONG")
    with arcpy.da.InsertCursor(out_pt_fc, ["SHAPE@", "X", "Y", "CNT"]) as ic:
        for x, y, c in uniq:
            ic.insertRow([arcpy.PointGeometry(arcpy.Point(x, y), sr), x, y, c])
    for t in (inter, single):
        arcpy.Delete_management(t)
    print(u"交点 -> %s（原始 %d 个，去重后 %d 个）"
          % (out_pt_fc, len(pts), len(uniq)))
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
