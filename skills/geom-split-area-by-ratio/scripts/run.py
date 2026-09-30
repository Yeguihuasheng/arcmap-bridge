# -*- coding: utf-8 -*-
"""
按重叠面积比例分摊属性（面积加权） —— ArcMap 版

把参照图层的数值属性按「重叠面积占参照图斑面积的比例」分摊到每个输入面要素上：输入面压住参照图斑多大比例，就拿多大比例的属性值，多块重叠求和。典型用法：把以行政区统计的人口/指标按面积加权摊到网格或地块上。

参数顺序（按地理处理工具原定义）：
  1. 输入面要素（接收分摊值的网格/地块）
  2. 参照面要素（带数值属性，如人口）
  3. 要分摊的数值字段（多个用分号分隔）
  4. 输出面要素（输入 + 分摊值字段）

用法：
    python run.py <输入面要素（接收分摊值的网格/地块）> <参照面要素（带数值属性，如人口）> <要分摊的数值字段（多个用分号分隔）> <输出面要素（输入 + 分摊值字段）>
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


def _is_num(v):
    return isinstance(v, _NUM) and not isinstance(v, bool)




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
        print(u"用法: python run.py <输入面要素（接收分摊值的网格/地块）> <参照面要素（带数值属性，如人口）> <要分摊的数值字段（多个用分号分隔）> <输出面要素（输入 + 分摊值字段）>")
        return 1
    in_poly_fc = argv[0]
    ref_poly_fc = argv[1]
    fields = argv[2]
    out_poly_fc = argv[3]
    arcpy.env.overwriteOutput = True
    flds = _split(fields)
    if not flds:
        raise ValueError(u"至少要给一个分摊字段")
    for f in flds:
        if not _has_field(ref_poly_fc, f):
            raise ValueError(u"参照面里没有字段: %s" % f)

    refs = []
    with arcpy.da.SearchCursor(ref_poly_fc, ["SHAPE@"] + flds) as cur:
        for row in cur:
            g = row[0]
            if g is None or g.area <= 0:
                continue
            vals = [v if _is_num(v) else None for v in row[1:]]
            refs.append((g, vals))
    if not refs:
        raise RuntimeError(u"参照面里没有有效要素")

    arcpy.CopyFeatures_management(in_poly_fc, out_poly_fc)
    out_names = []
    for f in flds:
        name = f if not _has_field(out_poly_fc, f) else u'AP_' + f
        name = name[:10] if out_poly_fc.lower().endswith(u'.shp') else name
        arcpy.AddField_management(out_poly_fc, name, "DOUBLE")
        out_names.append(name)

    n = 0
    with arcpy.da.UpdateCursor(out_poly_fc, ["SHAPE@"] + out_names) as cur:
        for row in cur:
            g = row[0]
            if g is None:
                continue
            totals = [0.0] * len(flds)
            for rg, rv in refs:
                try:
                    inter = g.intersect(rg, 4)
                except Exception:
                    continue
                if inter is None or inter.area <= 0:
                    continue
                ratio = inter.area / rg.area
                for i in range(len(flds)):
                    if rv[i] is not None:
                        totals[i] += rv[i] * ratio
            cur.updateRow([g] + totals)
            n += 1
    print(u"按分 -> %s（%d 个输入面，分摊字段: %s）"
          % (out_poly_fc, n, u'、'.join(out_names)))
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
