# -*- coding: utf-8 -*-
"""
文件夹栅格批量定义坐标系 —— ArcMap 版

遍历一个文件夹里的全部栅格，统一定义坐标系（只改元数据不重采样）。用于下载/导出的影像与 DEM 批量挂坐标系。注意：这是「定义」不是「投影」，坐标系本来就对的才能用。

参数顺序（按地理处理工具原定义）：
  1. 栅格所在文件夹（只处理第一层）
  2. 坐标系：工厂代码（如 4490）/ .prj 文件路径 / WKT 字符串

用法：
    python run.py <栅格所在文件夹（只处理第一层）> <坐标系：工厂代码（如 4490）/ .prj 文件路径 / WKT 字符串>
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

def _resolve_sr(text):
    """坐标系参数：工厂代码 / .prj 路径 / 坐标系名字符串。"""
    t = (text or u'').strip()
    sr = arcpy.SpatialReference()
    if t.isdigit():
        sr.factoryCode = int(t)
        sr.create()
        return sr
    if os.path.isfile(t):
        return arcpy.SpatialReference(t)
    sr.loadFromString(t)
    return sr




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
        print(u"用法: python run.py <栅格所在文件夹（只处理第一层）> <坐标系：工厂代码（如 4490）/ .prj 文件路径 / WKT 字符串>")
        return 1
    raster_folder = argv[0]
    sr_text = argv[1]
    if not os.path.isdir(raster_folder):
        raise ValueError(u"文件夹不存在: %s" % raster_folder)
    sr = _resolve_sr(sr_text)
    arcpy.env.workspace = raster_folder
    rasters = arcpy.ListRasters() or []
    if not rasters:
        print(u"该文件夹里没有栅格")
        return 0
    print(u"共 %d 个栅格，坐标系 -> %s" % (len(rasters), sr.name))
    done = 0
    had_sr = 0
    for r in rasters:
        try:
            old = arcpy.Describe(r).spatialReference
            if old and old.name != u'Unknown':
                had_sr += 1
                tag = u'（原来已有: %s，将被覆盖）' % old.name
            else:
                tag = u''
            arcpy.DefineProjection_management(r, sr)
            done += 1
            print(u"  %d/%d %s%s" % (done, len(rasters), r, tag))
        except Exception as e:
            print(u"  失败 %s: %s" % (r, e))
    print(u"完成: 成功定义 %d 个，其中 %d 个原来就带坐标系（已覆盖）"
          % (done, had_sr))
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
