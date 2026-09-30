# -*- coding: utf-8 -*-
"""
批量压缩地理数据库 —— ArcMap 版

扫描指定目录下的全部文件地理数据库（*.gdb），逐个执行 Compact 压缩，回收因频繁增删要素而膨胀的存储空间、降低体积。适用于项目收尾归档前的 GDB 批量瘦身。

参数顺序（按地理处理工具原定义）：
  1. 要扫描的目录（其下的 *.gdb 全部压缩）

用法：
    python run.py <要扫描的目录（其下的 *.gdb 全部压缩）>
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
    if len(argv) < 1:
        print(u"用法: python run.py <要扫描的目录（其下的 *.gdb 全部压缩）>")
        return 1
    gdb_dir = argv[0]
    if not os.path.isdir(gdb_dir):
        raise ValueError(u"目录不存在: %s" % gdb_dir)
    arcpy.env.workspace = gdb_dir
    gdbs = arcpy.ListWorkspaces(u'*', u'FileGDB')
    gdbs = [g for g in (gdbs or []) if g.lower().endswith(u'.gdb')]
    if not gdbs:
        raise ValueError(u"目录下没有找到任何 .gdb 文件地理数据库: %s" % gdb_dir)
    print(u"找到 %d 个 GDB，开始压缩" % len(gdbs))
    done = 0
    for idx, gdb in enumerate(gdbs, 1):
        try:
            arcpy.Compact_management(gdb)
            print(u"  [%d/%d] %s 压缩完成" % (idx, len(gdbs), os.path.basename(gdb)))
            done += 1
        except Exception as e:
            print(u"  [%d/%d] %s 失败: %s" % (idx, len(gdbs), os.path.basename(gdb), _u(e)))
    print(u"共压缩 %d/%d 个 GDB" % (done, len(gdbs)))
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
