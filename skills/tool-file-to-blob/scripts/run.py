# -*- coding: utf-8 -*-
"""
文件批量写入 BLOB 字段 —— ArcMap 版

按「文件名字段值 + 目录 + 扩展名」找到对应文件，把文件字节写入要素的 BLOB 字段。用于把外业照片按编号批量回挂到数据库记录上。与 `tool-blob-to-file` 互为逆操作。

参数顺序（按地理处理工具原定义）：
  1. 输入要素类或表（将被写入 BLOB）
  2. BLOB 字段名（已存在的 BLOB/Raster 类型字段）
  3. 文件名字段（其值 = 目录里的文件名，不含扩展名）
  4. 文件所在目录
  5. 文件扩展名（默认 .jpg）

用法：
    python run.py <输入要素类或表（将被写入 BLOB）> <BLOB 字段名（已存在的 BLOB/Raster 类型字段）> <文件名字段（其值 = 目录里的文件名，不含扩展名）> <文件所在目录> <文件扩展名（默认 .jpg）>
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
    if len(argv) < 5:
        print(u"用法: python run.py <输入要素类或表（将被写入 BLOB）> <BLOB 字段名（已存在的 BLOB/Raster 类型字段）> <文件名字段（其值 = 目录里的文件名，不含扩展名）> <文件所在目录> <文件扩展名（默认 .jpg）>")
        return 1
    in_fc = argv[0]
    blob_field = argv[1]
    name_field = argv[2]
    file_dir = argv[3]
    ext = argv[4]
    if not _has_field(in_fc, blob_field):
        raise ValueError(u"输入里没有 BLOB 字段: %s（请先建一个 BLOB 类型字段）" % blob_field)
    if not _has_field(in_fc, name_field):
        raise ValueError(u"输入里没有文件名字段: %s" % name_field)
    if not os.path.isdir(file_dir):
        raise ValueError(u"目录不存在: %s" % file_dir)
    e = (ext or u'.jpg').strip()
    if not e.startswith(u'.'):
        e = u'.' + e

    # 目录索引：小写文件名（不含扩展名）-> 全路径
    idx = {}
    for f in os.listdir(file_dir):
        if f.lower().endswith(e.lower()):
            idx[f[:-len(e)].lower()] = os.path.join(file_dir, f)

    done = 0
    miss = 0
    with arcpy.da.UpdateCursor(in_fc, [name_field, blob_field]) as cur:
        for row in cur:
            key = _u(row[0]).strip().lower()
            if not key:
                continue
            fp = idx.get(key)
            if fp is None:
                miss += 1
                if miss <= 10:
                    print(u"  找不到文件: %s%s" % (_u(row[0]).strip(), e))
                continue
            with open(fp, 'rb') as fh:
                row[1] = fh.read()
            cur.updateRow(row)
            done += 1
    print(u"写入完成: %d 条，未找到文件 %d 条" % (done, miss))
    if miss > 10:
        print(u"（其余 %d 条未找到文件的记录已省略）" % (miss - 10))
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
