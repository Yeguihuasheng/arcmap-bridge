# -*- coding: utf-8 -*-
"""
批量 GPX 转要素类 —— ArcMap 版

把一个目录下的全部 GPX 文件（手持 GPS / 户外 App 导出的航点、轨迹）批量转换为要素类（waypoint 转点、track/route 转线），并可选地把全部文件合并为一个总要素类。与 `tool-features-to-gpx`（要素导出 GPX）互为逆操作。

参数顺序（按地理处理工具原定义）：
  1. 含 .gpx 文件的目录
  2. 输出文件地理数据库（不存在则创建）
  3. 是否合并成一个总要素类：true / false

用法：
    python run.py <含 .gpx 文件的目录> <输出文件地理数据库（不存在则创建）> <是否合并成一个总要素类：true / false>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import glob
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
        print(u"用法: python run.py <含 .gpx 文件的目录> <输出文件地理数据库（不存在则创建）> <是否合并成一个总要素类：true / false>")
        return 1
    gpx_dir = argv[0]
    out_gdb = argv[1]
    merge_all = argv[2]
    if not os.path.isdir(gpx_dir):
        raise ValueError(u"GPX 目录不存在: %s" % gpx_dir)
    if not os.path.isdir(out_gdb):
        # 自动创建 GDB
        gdb_parent = os.path.dirname(out_gdb)
        gdb_name = os.path.basename(out_gdb)
        if not os.path.isdir(gdb_parent):
            os.makedirs(gdb_parent)
        arcpy.CreateFileGDB_management(gdb_parent, gdb_name)
    arcpy.env.overwriteOutput = True

    gpxs = sorted(glob.glob(os.path.join(gpx_dir, u'*.gpx')))
    if not gpxs:
        raise ValueError(u"目录下没有 .gpx 文件: %s" % gpx_dir)

    made = []
    for gpx in gpxs:
        base = os.path.splitext(os.path.basename(gpx))[0]
        out_fc = os.path.join(out_gdb, base)
        try:
            arcpy.GPXtoFeatures_conversion(gpx, out_fc)
            made.append(out_fc)
            print(u"  + %s -> %s" % (os.path.basename(gpx), base))
        except Exception as e:
            print(u"  x %s 转换失败: %s" % (os.path.basename(gpx), _u(e)))

    if not made:
        raise ValueError(u"没有任何 GPX 转换成功")

    if (merge_all or u'').strip().lower() in (u'true', u'1', u'yes', u'y', u'是'):
        if len(made) > 1:
            merged = os.path.join(out_gdb, u'all_runs')
            arcpy.Merge_management(made, merged)
            print(u"  + 合并 -> all_runs（%d 个文件）" % len(made))
        else:
            print(u"  只有一个文件，无需合并")
    print(u"完成：%d 个 GPX 转成要素类" % len(made))
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
