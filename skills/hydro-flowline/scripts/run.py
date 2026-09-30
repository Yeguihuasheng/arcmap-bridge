# -*- coding: utf-8 -*-
"""
河网按河段整编成河流线 —— ArcMap 版

把人工编辑过的河网（已删掉不分析的支流、ReachName 已填好）按 ReachName 融合成一条河段一根线，再做 PAEK 平滑，产出干净的 flowline 河流线。是纵剖面/横断面分析的基础线。

参数顺序（按地理处理工具原定义）：
  1. 输出要素数据集（成果放这里）
  2. 编辑好的河网要素类（带 ReachName 字段）
  3. PAEK 平滑容差（2~5 经验安全区，坐标系单位）

用法：
    python run.py <输出要素数据集（成果放这里）> <编辑好的河网要素类（带 ReachName 字段）> <PAEK 平滑容差（2~5 经验安全区，坐标系单位）>
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
    if len(argv) < 3:
        print(u"用法: python run.py <输出要素数据集（成果放这里）> <编辑好的河网要素类（带 ReachName 字段）> <PAEK 平滑容差（2~5 经验安全区，坐标系单位）>")
        return 1
    feature_dataset = argv[0]
    stream_network = argv[1]
    smooth_tolerance = float(argv[2])
    arcpy.env.overwriteOutput = True
    if not _has_field(stream_network, u'ReachName'):
        raise ValueError(u"河网里没有 ReachName 字段（按河段融合要用）")
    diss = os.path.join(feature_dataset, u'stream_network_dissolve')
    arcpy.Dissolve_management(stream_network, diss, u'ReachName', u'',
                              u'MULTI_PART')
    out = os.path.join(feature_dataset, u'flowline')
    arcpy.SmoothLine_cartography(diss, out, u'PAEK', smooth_tolerance)
    arcpy.Delete_management(diss)
    cnt = arcpy.GetCount_management(out).getOutput(0)
    print(u"河流线 -> %s（%s 条河段）" % (out, cnt))
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
