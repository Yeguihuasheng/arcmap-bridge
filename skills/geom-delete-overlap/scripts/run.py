# -*- coding: utf-8 -*-
"""
减去与参照图层的重叠部分 —— ArcMap 版

把输入要素与参照图层重叠的部分从几何上挖掉，输出"输入减去参照"的剩余部分，属性保留。例如从规划范围里挖掉已批红线、从林地图斑里挖掉建设用地。等价于 Erase，但**不需要 Advanced 许可**。

参数顺序（按地理处理工具原定义）：
  1. 输入要素（要被挖的）
  2. 参照要素（挖掉的范围）
  3. 输出剩余要素

用法：
    python run.py <输入要素（要被挖的）> <参照要素（挖掉的范围）> <输出剩余要素>
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
        print(u"用法: python run.py <输入要素（要被挖的）> <参照要素（挖掉的范围）> <输出剩余要素>")
        return 1
    in_fc = argv[0]
    ref_fc = argv[1]
    out_fc = argv[2]
    arcpy.env.overwriteOutput = True
    arcpy.CopyFeatures_management(in_fc, out_fc)
    diss = os.path.join(arcpy.env.scratchGDB, u'delovl_tmp')
    arcpy.Dissolve_management(ref_fc, diss, "", "", "SINGLE_PART")
    ref_geoms = []
    with arcpy.da.SearchCursor(diss, ["SHAPE@"]) as cur:
        for (g,) in cur:
            if g is not None and g.area > 0:
                ref_geoms.append(g)
    arcpy.Delete_management(diss)
    if not ref_geoms:
        print(u"参照图层没有有效面，输入原样输出")
        print(u"完成")
        return 0

    changed = 0
    with arcpy.da.UpdateCursor(out_fc, ["SHAPE@"]) as cur:
        for (g,) in cur:
            if g is None:
                continue
            ng = g
            for r in ref_geoms:
                try:
                    ng = ng.difference(r)
                except Exception:
                    pass
            if ng is not g:
                try:
                    cur.updateRow([ng])
                    changed += 1
                except Exception:
                    pass
    print(u"挖除 -> %s（改动 %d 个要素，参照融合为 %d 块）"
          % (out_fc, changed, len(ref_geoms)))
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
