# -*- coding: utf-8 -*-
"""
工作空间数据集范围转面 —— ArcMap 版

遍历一个工作空间（GDB/文件夹）里的全部要素类与栅格，把每个数据集的空间范围生成一个矩形面，带数据集名与类型字段。用于快速制作数据覆盖范围索引图、检查成果空间分布。

参数顺序（按地理处理工具原定义）：
  1. 输入工作空间（GDB 路径或文件夹）
  2. 输出范围面要素

用法：
    python run.py <输入工作空间（GDB 路径或文件夹）> <输出范围面要素>
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
    if len(argv) < 2:
        print(u"用法: python run.py <输入工作空间（GDB 路径或文件夹）> <输出范围面要素>")
        return 1
    in_ws = argv[0]
    out_fc = argv[1]
    arcpy.env.overwriteOutput = True
    if not arcpy.Exists(in_ws):
        raise ValueError(u"工作空间不存在: %s" % in_ws)
    old = arcpy.env.workspace
    arcpy.env.workspace = in_ws

    items = []
    for fc in (arcpy.ListFeatureClasses() or []):
        items.append((fc, u'FeatureClass'))
    for r in (arcpy.ListRasters() or []):
        items.append((r, u'RasterDataset'))
    for fd in (arcpy.ListDatasets(u'', u'Feature') or []):
        for fc in (arcpy.ListFeatureClasses(u'', u'', fd) or []):
            items.append((fc, u'FeatureClass'))
    arcpy.env.workspace = old
    if not items:
        print(u"该工作空间里没有要素类或栅格")
        return 0

    sr = None
    infos = []
    for name, typ in items:
        try:
            d = arcpy.Describe(name)
            ext = d.extent
            if sr is None:
                sr = d.spatialReference
            infos.append((_u(d.baseName), typ, _u(d.catalogPath), ext, d))
        except Exception as e:
            print(u"  读取失败 %s: %s" % (name, e))
    if not infos:
        raise RuntimeError(u"没有可读的数据集")

    out_dir, out_name = os.path.split(out_fc)
    if not out_dir:
        out_dir = arcpy.env.workspace
    arcpy.CreateFeatureclass_management(out_dir, out_name, "POLYGON",
                                        "", "", "", sr)
    arcpy.AddField_management(out_fc, "DS_NAME", "TEXT", "", "", 200)
    arcpy.AddField_management(out_fc, "DS_TYPE", "TEXT", "", "", 30)
    arcpy.AddField_management(out_fc, "DS_PATH", "TEXT", "", "", 500)
    arcpy.AddField_management(out_fc, "FCOUNT", "LONG")

    def _mk(ext, target_sr):
        if target_sr is not None:
            try:
                ext = ext.projectAs(target_sr)
            except Exception:
                pass
        arr = arcpy.Array([arcpy.Point(ext.XMin, ext.YMin),
                           arcpy.Point(ext.XMax, ext.YMin),
                           arcpy.Point(ext.XMax, ext.YMax),
                           arcpy.Point(ext.XMin, ext.YMax),
                           arcpy.Point(ext.XMin, ext.YMin)])
        return arcpy.Polygon(arr, target_sr)

    with arcpy.da.InsertCursor(out_fc, ["SHAPE@", "DS_NAME", "DS_TYPE",
                                        "DS_PATH", "FCOUNT"]) as ic:
        for base, typ, path, ext, d in infos:
            try:
                cnt = int(arcpy.GetCount_management(path).getOutput(0))
            except Exception:
                cnt = None
            ic.insertRow([_mk(ext, sr), base, typ, path, cnt])
    print(u"范围面 -> %s（%d 个数据集）" % (out_fc, len(infos)))
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
