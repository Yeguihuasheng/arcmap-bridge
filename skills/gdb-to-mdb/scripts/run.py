# -*- coding: utf-8 -*-
"""
文件地理数据库批量转个人地理数据库 —— ArcMap 版

把指定目录下的全部文件地理数据库（*.gdb）批量转换为个人地理数据库（*.mdb，Access 格式），每个源 GDB 对应一个同名 MDB。适用于需要与老版本 ArcMap（9.x/10.x 早期）或只用 Access 的协作方交换数据的场景。

参数顺序（按地理处理工具原定义）：
  1. 源目录（其下 *.gdb 全部转换）
  2. 输出目录（存放生成的 *.mdb）

用法：
    python run.py <源目录（其下 *.gdb 全部转换）> <输出目录（存放生成的 *.mdb）>
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
    if len(argv) < 2:
        print(u"用法: python run.py <源目录（其下 *.gdb 全部转换）> <输出目录（存放生成的 *.mdb）>")
        return 1
    gdb_dir = argv[0]
    mdb_dir = argv[1]
    if not os.path.isdir(gdb_dir):
        raise ValueError(u"源目录不存在: %s" % gdb_dir)
    if not os.path.isdir(mdb_dir):
        os.makedirs(mdb_dir)
    arcpy.env.workspace = gdb_dir
    gdbs = [g for g in (arcpy.ListWorkspaces(u'*', u'FileGDB') or [])
            if g.lower().endswith(u'.gdb')]
    if not gdbs:
        raise ValueError(u"源目录下没有 .gdb 文件地理数据库: %s" % gdb_dir)
    arcpy.env.overwriteOutput = True

    done = 0
    for idx, gdb in enumerate(gdbs, 1):
        base = os.path.splitext(os.path.basename(gdb))[0]
        mdb = os.path.join(mdb_dir, base + u'.mdb')
        if arcpy.Exists(mdb):
            arcpy.Delete_management(mdb)
        try:
            arcpy.CreatePersonalGDB_management(mdb_dir, base + u'.mdb')
            arcpy.env.workspace = gdb
            fcs = arcpy.ListFeatureClasses()
            if fcs:
                arcpy.FeatureClassToGeodatabase_conversion(fcs, mdb)
            print(u"  [%d/%d] %s -> %s.mdb（%d 个要素类）" % (idx, len(gdbs), base, base, len(fcs or [])))
            done += 1
        except Exception as e:
            print(u"  [%d/%d] %s 转换失败: %s" % (idx, len(gdbs), base, _u(e)))
    print(u"完成：%d/%d 个 GDB 转成 MDB" % (done, len(gdbs)))
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
