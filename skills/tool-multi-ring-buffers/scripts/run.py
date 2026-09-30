# -*- coding: utf-8 -*-
"""
多环缓冲（含负值内缩） —— ArcMap 版

按一组距离（如 100;200;500，支持负值=面向内收缩）逐个生成缓冲，每环的距离写进 DIST 字段，最后合并成一个面要素类。用于圈层分析（0-100 / 100-200 / 200-500 影响带）、由近及远的设施辐射分级，负距离可做面内核/边缘带。

参数顺序（按地理处理工具原定义）：
  1. 输入要素（点/线/面）
  2. 缓冲距离列表，分号分隔（如 100;200;500；负值=向内收缩）
  3. 输出多环面要素
  4. 融合字段（分号分隔；填 NONE=不融合只叠环；填 ALL=全部融合）

用法：
    python run.py <输入要素（点/线/面）> <缓冲距离列表，分号分隔（如 100;200;500；负值=向内收缩）> <输出多环面要素> <融合字段（分号分隔；填 NONE=不融合只叠环；填 ALL=全部融合）>
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
    if len(argv) < 4:
        print(u"用法: python run.py <输入要素（点/线/面）> <缓冲距离列表，分号分隔（如 100;200;500；负值=向内收缩）> <输出多环面要素> <融合字段（分号分隔；填 NONE=不融合只叠环；填 ALL=全部融合）>")
        return 1
    in_fc = argv[0]
    distances = argv[1]
    out_fc = argv[2]
    dissolve = argv[3]
    arcpy.env.overwriteOutput = True
    dists = _split(distances)
    if not dists:
        raise ValueError(u"至少给一个缓冲距离")
    nums = []
    for d in dists:
        try:
            nums.append(float(d))
        except ValueError:
            raise ValueError(u"距离不是数字: %s" % d)
    if any(x == 0 for x in nums):
        raise ValueError(u"距离不能为 0")

    dv = (dissolve or u'NONE').strip().upper()
    if dv == u'ALL':
        diss_fields = u'#'
        diss_type = u'LIST'
    elif dv in (u'NONE', u'#', u''):
        diss_fields = u''
        diss_type = u'NONE'
    else:
        diss_fields = u';'.join(_split(dissolve))
        diss_type = u'LIST'

    parts = []
    for i, d in enumerate(nums):
        tmp = r'in_memory\mrb_%d' % i
        arcpy.Buffer_analysis(in_fc, tmp, d, u'FULL', u'ROUND',
                              diss_type, diss_fields)
        arcpy.AddField_management(tmp, "DIST", "DOUBLE")
        arcpy.CalculateField_management(tmp, "DIST", repr(d), "PYTHON")
        parts.append(tmp)
    arcpy.Merge_management(parts, out_fc)
    for t in parts:
        arcpy.Delete_management(t)
    cnt = arcpy.GetCount_management(out_fc).getOutput(0)
    print(u"多环缓冲 -> %s（%d 环共 %s 个要素）" % (out_fc, len(nums), cnt))
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
