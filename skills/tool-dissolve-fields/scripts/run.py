# -*- coding: utf-8 -*-
"""
按字段融合并拼接文本清单 —— ArcMap 版

按分组字段融合要素，同时把指定的文本字段值去重拼接成清单（如「甲村;乙村;丙村」）写进结果。解决标准 Dissolve 只能给统计值、把文本清单丢掉的问题：融合一个乡镇面，同时保留它包含的全部村庄名单。

参数顺序（按地理处理工具原定义）：
  1. 输入要素
  2. 融合字段（分号分隔）
  3. 要拼接清单的文本字段（分号分隔）
  4. 输出融合要素
  5. 清单分隔符（默认 ;）

用法：
    python run.py <输入要素> <融合字段（分号分隔）> <要拼接清单的文本字段（分号分隔）> <输出融合要素> <清单分隔符（默认 ;）>
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
        print(u"用法: python run.py <输入要素> <融合字段（分号分隔）> <要拼接清单的文本字段（分号分隔）> <输出融合要素> <清单分隔符（默认 ;）>")
        return 1
    in_fc = argv[0]
    dissolve_fields = argv[1]
    concat_fields = argv[2]
    out_fc = argv[3]
    sep = argv[4]
    arcpy.env.overwriteOutput = True
    df = _split(dissolve_fields)
    cf = _split(concat_fields)
    if not df:
        raise ValueError(u"至少给一个融合字段")
    if not cf:
        raise ValueError(u"至少给一个拼接字段")
    for f in df + cf:
        if not _has_field(in_fc, f):
            raise ValueError(u"输入里没有字段: %s" % f)
    sp = (sep or u';').strip() or u';'

    # 先收集每组的清单
    groups = {}
    order = []
    with arcpy.da.SearchCursor(in_fc, df + cf) as cur:
        for row in cur:
            key = tuple(_u(v) for v in row[:len(df)])
            if key not in groups:
                groups[key] = [[] for _ in cf]
                order.append(key)
            for i in range(len(cf)):
                v = _u(row[len(df) + i])
                lst = groups[key][i]
                if v != u'' and v not in lst:  # 保序去重：按源数据出现顺序
                    lst.append(v)

    # 融合（不带统计字段）
    arcpy.Dissolve_management(in_fc, out_fc, u';'.join(df), "",
                              "SINGLE_PART")
    # 输出补拼接字段
    out_names = []
    for f in cf:
        nm = u'CAT_' + f
        nm = nm[:10] if out_fc.lower().endswith(u'.shp') else nm
        while _has_field(out_fc, nm):
            nm += u'_'
        arcpy.AddField_management(out_fc, nm, "TEXT", "", "", 4000)
        out_names.append(nm)

    with arcpy.da.UpdateCursor(out_fc, df + out_names) as cur:
        for row in cur:
            key = tuple(_u(v) for v in row[:len(df)])
            cat = groups.get(key)
            vals = list(row)
            if cat:
                for i in range(len(cf)):
                    vals[len(df) + i] = sp.join(cat[i])
            cur.updateRow(vals)
    print(u"融合拼接 -> %s（%d 组，拼接字段: %s）"
          % (out_fc, len(order), u'、'.join(out_names)))
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
