# -*- coding: utf-8 -*-
"""
BLOB 字段批量导出文件 —— ArcMap 版

读取要素类 BLOB 字段里的二进制内容（照片、PDF、签名图等），按记录逐条导出成本地文件，文件名取自指定字段值（无该值时用 OID）。用于把外业照片、巡查影像从库中批量落盘整理。

参数顺序（按地理处理工具原定义）：
  1. 输入要素类或表（含 BLOB 字段）
  2. BLOB 字段名
  3. 文件名字段（取其值做文件名；填 # 用 OID）
  4. 导出目录
  5. 文件扩展名（默认 .jpg）

用法：
    python run.py <输入要素类或表（含 BLOB 字段）> <BLOB 字段名> <文件名字段（取其值做文件名；填 # 用 OID）> <导出目录> <文件扩展名（默认 .jpg）>
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

_BAD = u'\\/:*?"<>|'


def _safe_name(s):
    out = u''.join(u'_' if ch in _BAD else ch for ch in _u(s)).strip()
    return out or u'noname'




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
        print(u"用法: python run.py <输入要素类或表（含 BLOB 字段）> <BLOB 字段名> <文件名字段（取其值做文件名；填 # 用 OID）> <导出目录> <文件扩展名（默认 .jpg）>")
        return 1
    in_fc = argv[0]
    blob_field = argv[1]
    name_field = argv[2]
    out_dir = argv[3]
    ext = argv[4]
    if not _has_field(in_fc, blob_field):
        raise ValueError(u"输入里没有 BLOB 字段: %s" % blob_field)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    e = (ext or u'.jpg').strip()
    if not e.startswith(u'.'):
        e = u'.' + e

    nf = (name_field or u'').strip()
    if nf == u'#' or not nf:
        nf = None
    cols = [u'OID@', blob_field] + ([nf] if nf else [])
    used = {}
    done = 0
    empty = 0
    with arcpy.da.SearchCursor(in_fc, cols) as cur:
        for row in cur:
            oid, blob = row[0], row[1]
            base = _safe_name(row[2]) if nf and row[2] not in (None, u'') else u'rec_%s' % oid
            if blob is None:
                empty += 1
                continue
            if isinstance(blob, (bytearray, memoryview)):
                # py2 的 da 游标把 BLOB 读成 memoryview；bytes(mv) 在 py2
                # 会拿到 repr 字符串（22 字节），必须经 bytearray 中转提取
                blob = bytes(bytearray(blob))
            elif not isinstance(blob, bytes):
                try:
                    blob = str(blob)
                except Exception:
                    blob = u''
            name = base + e
            k = 1
            while name in used:
                k += 1
                name = u'%s_%d%s' % (base, k, e)
            used[name] = True
            fp = os.path.join(out_dir, name)
            with open(fp, 'wb') as fh:
                fh.write(blob)
            done += 1
    print(u"导出 -> %s（%d 个文件，空值跳过 %d 条）" % (out_dir, done, empty))
    if empty:
        print(u"提示: %d 条记录 BLOB 为空" % empty)
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
