# -*- coding: utf-8 -*-
"""
沿线路生成地形剖面 —— ArcMap 版

沿一条（或一组）线要素在 DEM/表面上采样，生成剖面数据表（每行 = 线上某位置的 X/Y/距起点距离/高程），并可把剖面图导出成图片文件。用于道路纵断面、管线埋深、视线分析的快速取值。

参数顺序（按地理处理工具原定义）：
  1. 表面栅格（DEM）
  2. 剖面线要素
  3. 输出剖面数据表（GDB 表或 CSV 均可）
  4. 剖面图导出文件（如 .jpg/.png；填 # 只要表不要图）

用法：
    python run.py <表面栅格（DEM）> <剖面线要素> <输出剖面数据表（GDB 表或 CSV 均可）> <剖面图导出文件（如 .jpg/.png；填 # 只要表不要图）>
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
        print(u"用法: python run.py <表面栅格（DEM）> <剖面线要素> <输出剖面数据表（GDB 表或 CSV 均可）> <剖面图导出文件（如 .jpg/.png；填 # 只要表不要图）>")
        return 1
    dem = argv[0]
    line_fc = argv[1]
    out_table = argv[2]
    out_graph = argv[3]
    if arcpy.CheckExtension('3D') != 'Available':
        raise RuntimeError(u"需要 3D Analyst 扩展许可")
    arcpy.CheckOutExtension('3D')
    try:
        arcpy.env.overwriteOutput = True
        arcpy.StackProfile_3d(line_fc, dem, out_table, u'剖面图')
        cnt = arcpy.GetCount_management(out_table).getOutput(0)
        print(u"剖面表 -> %s（%s 个采样点）" % (out_table, cnt))
        og = (out_graph or u'').strip()
        if og and og != u'#':
            try:
                arcpy.SaveGraph_management(u'剖面图', og)
                print(u"剖面图 -> %s" % og)
            except Exception as e:
                print(u"剖面图导出失败（%s）" % e)
                print(u"表已生成，可在 ArcMap 里用剖面结果手动出图")
    finally:
        arcpy.CheckInExtension('3D')
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
