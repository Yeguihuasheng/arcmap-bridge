# -*- coding: utf-8 -*-
"""
文件夹栅格批量定义 NoData 值 —— ArcMap 版

遍历一个文件夹里的全部栅格，统一把指定值登记为 NoData（只改元数据，不改像元值）。最典型的是 8 位影像把 255（白边）登记为 NoData，让镶嵌/裁剪/统计自动忽略背景。

参数顺序（按地理处理工具原定义）：
  1. 栅格所在文件夹（只处理第一层）
  2. NoData 定义，格式「波段号 值」，多波段用分号（默认 1 255）

用法：
    python run.py <栅格所在文件夹（只处理第一层）> <NoData 定义，格式「波段号 值」，多波段用分号（默认 1 255）>
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
        print(u"用法: python run.py <栅格所在文件夹（只处理第一层）> <NoData 定义，格式「波段号 值」，多波段用分号（默认 1 255）>")
        return 1
    raster_folder = argv[0]
    nodata_spec = argv[1]
    if not os.path.isdir(raster_folder):
        raise ValueError(u"文件夹不存在: %s" % raster_folder)
    spec = (nodata_spec or u'').strip() or u'1 255'
    for seg in spec.split(u';'):
        seg = seg.strip()
        if seg and len(seg.split()) != 2:
            raise ValueError(u"NoData 定义每项应为『波段号 值』，实际: %s" % seg)
    arcpy.env.workspace = raster_folder
    rasters = arcpy.ListRasters() or []
    if not rasters:
        print(u"该文件夹里没有栅格")
        return 0
    print(u"共 %d 个栅格，NoData 定义 -> %s" % (len(rasters), spec))
    done = 0
    for r in rasters:
        try:
            arcpy.SetRasterProperties_management(r, "GENERIC", "", "", spec)
            done += 1
        except Exception as e:
            print(u"  失败 %s: %s" % (r, e))
    for r in rasters:
        try:
            arcpy.CalculateStatistics_management(r)
        except Exception:
            pass
    print(u"完成: 成功登记 %d/%d 个" % (done, len(rasters)))
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
