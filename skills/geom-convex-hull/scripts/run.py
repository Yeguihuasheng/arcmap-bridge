# -*- coding: utf-8 -*-
"""
按分组生成凸包 —— ArcMap 版

按分组字段把点要素分组，每组生成一个凸包（最小凸多边形），可再按指定距离向外扩一圈缓冲。用于圈定点群的外围轮廓、设施影响包络、动物活动范围等；不带分组字段时把全部点合成一个凸包。

参数顺序（按地理处理工具原定义）：
  1. 输入点要素
  2. 输出凸包面要素
  3. 分组字段（填 # 表示全部点合成一个凸包）
  4. 凸包外扩缓冲距离（如 100 Meters；填 # 不缓冲）

用法：
    python run.py <输入点要素> <输出凸包面要素> <分组字段（填 # 表示全部点合成一个凸包）> <凸包外扩缓冲距离（如 100 Meters；填 # 不缓冲）>
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
    if len(argv) < 4:
        print(u"用法: python run.py <输入点要素> <输出凸包面要素> <分组字段（填 # 表示全部点合成一个凸包）> <凸包外扩缓冲距离（如 100 Meters；填 # 不缓冲）>")
        return 1
    in_pt_fc = argv[0]
    out_poly_fc = argv[1]
    group_field = argv[2]
    buffer_dist = argv[3]
    arcpy.env.overwriteOutput = True
    gf = (group_field or u'').strip()
    tmp = r'in_memory\hull_tmp'
    if gf != u'#' and gf:
        if not _has_field(in_pt_fc, gf):
            raise ValueError(u"输入点要素里没有分组字段: %s" % gf)
        arcpy.MinimumBoundingGeometry_management(
            in_pt_fc, tmp, "CONVEX_HULL", "LIST", gf)
    else:
        arcpy.MinimumBoundingGeometry_management(
            in_pt_fc, tmp, "CONVEX_HULL", "ALL")

    bd = (buffer_dist or u'').strip()
    if bd and bd != u'#':
        arcpy.Buffer_analysis(tmp, out_poly_fc, bd)
    else:
        arcpy.CopyFeatures_management(tmp, out_poly_fc)
    arcpy.Delete_management(tmp)
    cnt = arcpy.GetCount_management(out_poly_fc).getOutput(0)
    print(u"凸包 -> %s（%s 个）" % (out_poly_fc, cnt))
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
