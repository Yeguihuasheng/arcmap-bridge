# -*- coding: utf-8 -*-
"""
导出数据集结构清单 —— ArcMap 版

把要素类/表的字段结构（名称、别名、类型、长度、精度、小数位、是否必填、是否可空、默认值、属性域）导出成 CSV，用于入库前后的结构备案与比对。

参数顺序（按地理处理工具原定义）：
  1. 输入要素类或表
  2. 输出 CSV 路径

用法：
    python run.py <输入要素类或表> <输出 CSV 路径>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import csv
import arcpy


def _s(v):
    """任意值转 unicode 文本（py2/py3 通用，中文安全）"""
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


def write_csv(path, header, rows):
    """写 CSV：py2 走二进制模式，py3 走文本模式 + utf-8-sig（Excel 可直接开）"""
    if sys.version_info[0] >= 3:
        import io as _io
        fh = _io.open(path, 'w', newline='', encoding='utf-8-sig')
    else:
        fh = open(path, 'wb')
    try:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            w.writerow([_s(v) for v in r])
    finally:
        fh.close()




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
        print(u"用法: python run.py <输入要素类或表> <输出 CSV 路径>")
        return 1
    in_dataset = argv[0]
    out_csv = argv[1]
    if not arcpy.Exists(in_dataset):
        raise ValueError(u"数据集不存在: %s" % in_dataset)

    rows = []
    for f in arcpy.ListFields(in_dataset):
        rows.append([f.name, f.aliasName, f.type, f.length, f.precision,
                     f.scale, f.required, f.editable, f.isNullable,
                     f.defaultValue, f.domain])
    rows.sort(key=lambda r: _s(r[0]).lower())
    write_csv(out_csv,
              ['name', 'alias', 'type', 'length', 'precision', 'scale',
               'required', 'editable', 'nullable', 'default', 'domain'],
              rows)
    print(u"输出: %s，共 %d 个字段" % (out_csv, len(rows)))
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
