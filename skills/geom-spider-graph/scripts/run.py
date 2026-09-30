# -*- coding: utf-8 -*-
"""
生成蜘蛛图（点到最近参照点连线） —— ArcMap 版

为每个输入点找到**最近的**一个参照点，生成两点之间的连线，输出带起点/终点编号与距离的线要素。用于「每个居民点到最近学校」「每个地块到最近取土点」这类最近服务设施连线分析（比 OD 矩阵直观，出图即"蜘蛛网"）。

参数顺序（按地理处理工具原定义）：
  1. 输入点要素（每个点找一条连线）
  2. 参照点要素（学校/站点/设施）
  3. 输出连线要素

用法：
    python run.py <输入点要素（每个点找一条连线）> <参照点要素（学校/站点/设施）> <输出连线要素>
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
        print(u"用法: python run.py <输入点要素（每个点找一条连线）> <参照点要素（学校/站点/设施）> <输出连线要素>")
        return 1
    in_pt_fc = argv[0]
    ref_pt_fc = argv[1]
    out_line_fc = argv[2]
    arcpy.env.overwriteOutput = True
    refs = []
    with arcpy.da.SearchCursor(ref_pt_fc, ["OID@", "SHAPE@"]) as cur:
        for oid, g in cur:
            if g is not None:
                refs.append((oid, g))
    if not refs:
        raise RuntimeError(u"参照点要素里没有要素")

    sr = arcpy.Describe(in_pt_fc).spatialReference
    out_dir, out_name = os.path.split(out_line_fc)
    if not out_dir:
        out_dir = arcpy.env.workspace
    arcpy.CreateFeatureclass_management(out_dir, out_name, "POLYLINE",
                                        "", "", "", sr)
    arcpy.AddField_management(out_line_fc, "FROM_OID", "LONG")
    arcpy.AddField_management(out_line_fc, "TO_OID", "LONG")
    arcpy.AddField_management(out_line_fc, "DIST", "DOUBLE")

    n_in = int(arcpy.GetCount_management(in_pt_fc).getOutput(0))
    if n_in > 10000:
        print(u"提示: 输入点 %d 个，超过 1 万会较慢，请耐心等待" % n_in)

    made = 0
    zero = 0
    with arcpy.da.InsertCursor(out_line_fc,
                               ["SHAPE@", "FROM_OID", "TO_OID", "DIST"]) as ic:
        with arcpy.da.SearchCursor(in_pt_fc, ["OID@", "SHAPE@"]) as cur:
            for oid, g in cur:
                if g is None:
                    continue
                best = None
                for roid, rg in refs:
                    d = g.distanceTo(rg)
                    if d == 0:
                        continue
                    if best is None or d < best[2]:
                        best = (roid, rg, d)
                if best is None:
                    zero += 1
                    continue
                p1 = g.firstPoint
                p2 = best[1].firstPoint
                line = arcpy.Polyline(arcpy.Array(
                    [arcpy.Point(p1.X, p1.Y), arcpy.Point(p2.X, p2.Y)]), sr)
                ic.insertRow([line, oid, best[0], best[2]])
                made += 1
    print(u"蜘蛛线 -> %s（%d 条）" % (out_line_fc, made))
    if zero:
        print(u"有 %d 个输入点与参照点完全重合，未生成连线" % zero)
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
