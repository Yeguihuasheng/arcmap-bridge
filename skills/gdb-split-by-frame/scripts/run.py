# -*- coding: utf-8 -*-
"""
按分区范围拆分地理数据库 —— ArcMap 版

以一个分区多边形图层为界，把源 GDB 里的全部要素类逐分区裁剪，每个分区输出一个独立的文件地理数据库（库内要素类名与源一致）。适用于把全县数据按乡镇/图幅范围拆成多份交付。

参数顺序（按地理处理工具原定义）：
  1. 源文件地理数据库（含待拆分要素类）
  2. 分区多边形图层（每个要素 = 一个分区）
  3. 分区命名/标识字段（用于命名输出 GDB）
  4. 输出目录（每个分区在此建一个 .gdb）

用法：
    python run.py <源文件地理数据库（含待拆分要素类）> <分区多边形图层（每个要素 = 一个分区）> <分区命名/标识字段（用于命名输出 GDB）> <输出目录（每个分区在此建一个 .gdb）>
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
        print(u"用法: python run.py <源文件地理数据库（含待拆分要素类）> <分区多边形图层（每个要素 = 一个分区）> <分区命名/标识字段（用于命名输出 GDB）> <输出目录（每个分区在此建一个 .gdb）>")
        return 1
    input_gdb = argv[0]
    frame_fc = argv[1]
    split_field = argv[2]
    output_dir = argv[3]
    if not arcpy.Exists(input_gdb):
        raise ValueError(u"源 GDB 不存在: %s" % input_gdb)
    if not arcpy.Exists(frame_fc):
        raise ValueError(u"分区图层不存在: %s" % frame_fc)
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    arcpy.env.overwriteOutput = True

    arcpy.env.workspace = input_gdb
    fcs = arcpy.ListFeatureClasses()
    if not fcs:
        raise ValueError(u"源 GDB 里没有要素类: %s" % input_gdb)

    # 收集分区字段值
    names = []
    rows = arcpy.da.SearchCursor(frame_fc, [split_field])
    try:
        for (v,) in rows:
            s = _u(v).strip()
            if s and s not in names:
                names.append(s)
    finally:
        del rows

    if not names:
        raise ValueError(u"分区字段 %s 没有读到任何非空值" % split_field)

    print(u"分区数 %d，源要素类 %d 个" % (len(names), len(fcs)))
    import re
    for idx, name in enumerate(names, 1):
        safe = re.sub(u'[^0-9A-Za-z_\u4e00-\u9fa5]+', u'_', name)
        out_gdb = os.path.join(output_dir, safe + u'.gdb')
        if not arcpy.Exists(out_gdb):
            arcpy.CreateFileGDB_management(output_dir, safe + u'.gdb')
        # 选出该分区面
        where = u"%s = '%s'" % (split_field, name.replace(u"'", u"''"))
        arcpy.MakeFeatureLayer_management(frame_fc, u'frame_lyr', where)
        for fcidx, fc in enumerate(fcs, 1):
            out_fc = os.path.join(out_gdb, fc)
            try:
                arcpy.Clip_analysis(os.path.join(input_gdb, fc),
                                    u'frame_lyr', out_fc)
            except Exception as e:
                print(u"  [%d/%d] %s/%s 裁剪失败: %s" % (idx, len(names), safe, fc, _u(e)))
                continue
            print(u"  [%d/%d][%d/%d] %s / %s" % (idx, len(names), fcidx, len(fcs), safe, fc))
        arcpy.Delete_management(u'frame_lyr')
    print(u"拆分完成，输出 %d 个 GDB 到 %s" % (len(names), output_dir))
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
