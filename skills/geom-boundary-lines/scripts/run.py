# -*- coding: utf-8 -*-
"""
提取图斑边界线 —— ArcMap 版

把面要素的边界提取成线要素类，并保留原要素的属性字段，常用于生成地类界线、行政界线。

参数顺序（按地理处理工具原定义）：
  1. 输入面要素类
  2. 输出线要素类

用法：
    python run.py <输入面要素类> <输出线要素类>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import arcpy







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
        print(u"用法: python run.py <输入面要素类> <输出线要素类>")
        return 1
    in_features = argv[0]
    out_lines = argv[1]
    arcpy.env.overwriteOutput = True
    sr = arcpy.Describe(in_features).spatialReference
    geoms = []
    with arcpy.da.SearchCursor(in_features, ['SHAPE@']) as cursor:
        for row in cursor:
            if row[0] is None:
                continue
            bnd = row[0].boundary()
            if bnd is not None:
                geoms.append(bnd)
    if not geoms:
        raise ValueError(u"没有提取到任何边界，请检查输入是否为有效面要素")

    arcpy.CopyFeatures_management(geoms, out_lines)
    print(u"输出: %s，共 %d 条边界线" % (out_lines, len(geoms)))
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
