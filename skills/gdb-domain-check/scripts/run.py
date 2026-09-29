# -*- coding: utf-8 -*-
"""
属性域合规检查 —— ArcMap 版

逐字段检查数据取值是否落在属性域范围内（编码值域/数值区间），输出违规清单 CSV，是入库前值域体检的常用手段。

参数顺序（按地理处理工具原定义）：
  1. 输入要素类或表
  2. 输出违规清单 CSV（无违规时输出空表）

用法：
    python run.py <输入要素类或表> <输出违规清单 CSV（无违规时输出空表）>
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
        print(u"用法: python run.py <输入要素类或表> <输出违规清单 CSV（无违规时输出空表）>")
        return 1
    in_dataset = argv[0]
    out_csv = argv[1]
    if not arcpy.Exists(in_dataset):
        raise ValueError(u"数据集不存在: %s" % in_dataset)

    ws = arcpy.Describe(in_dataset).path
    domains = dict((d.name, d) for d in arcpy.da.ListDomains(ws))
    targets = [(f.name, f.domain) for f in arcpy.ListFields(in_dataset)
               if f.domain and f.domain in domains]
    if not targets:
        print(u"该数据集没有任何字段绑定属性域，无需检查")
        return 0

    bad = []
    names = [t[0] for t in targets]
    with arcpy.da.SearchCursor(in_dataset, ['OID@'] + names) as cursor:
        for row in cursor:
            oid = row[0]
            for i, fname in enumerate(names):
                val = row[i + 1]
                dom = domains[targets[i][1]]
                if val is None:
                    continue
                if dom.domainType == 'CodedValue':
                    if val not in dom.codedValues:
                        bad.append([oid, fname, _s(val),
                                    u'不在编码值域内'])
                else:
                    lo, hi = dom.range[0], dom.range[1]
                    try:
                        v = float(val)
                    except Exception:
                        bad.append([oid, fname, _s(val), u'非数值，无法比对区间'])
                        continue
                    if v < lo or v > hi:
                        bad.append([oid, fname, _s(val),
                                    u'超出区间 %s~%s' % (lo, hi)])

    write_csv(out_csv, ['oid', 'field', 'value', 'reason'], bad)
    print(u"检查字段 %d 个，发现违规 %d 处 -> %s" % (len(names), len(bad), out_csv))
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
