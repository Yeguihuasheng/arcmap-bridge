# -*- coding: utf-8 -*-
"""
生成泰森多边形 —— ArcMap 版

为每个点生成最近邻分配面（泰森/Voronoi 多边形）：面内任意位置到本点的距离都比到其它点近。用于服务区划分、站点影响范围、监测点位覆盖分区。

参数顺序（按地理处理工具原定义）：
  1. 输入点要素
  2. 输出泰森面要素

用法：
    python run.py <输入点要素> <输出泰森面要素>
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
    if len(argv) < 2:
        print(u"用法: python run.py <输入点要素> <输出泰森面要素>")
        return 1
    in_pt_fc = argv[0]
    out_poly_fc = argv[1]
    arcpy.env.overwriteOutput = True
    arcpy.CreateThiessenPolygons_analysis(in_pt_fc, out_poly_fc, "ALL")
    cnt = arcpy.GetCount_management(out_poly_fc).getOutput(0)
    n_in = arcpy.GetCount_management(in_pt_fc).getOutput(0)
    print(u"泰森面 -> %s（%s 个，输入点 %s 个）" % (out_poly_fc, cnt, n_in))
    if int(cnt) < int(n_in):
        print(u"提示: 输出面数少于点数，说明存在重合点（重合点只生成一个面）")
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
