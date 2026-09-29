# -*- coding: utf-8 -*-
"""
按字段分组求质心 —— ArcMap 版

把面要素先按指定字段融合分组，再求每组的质心点，输出点要素类。常用于把同属性的分散图斑归并后取代表点（如按行政村、按地类取中心点）。

参数顺序（按地理处理工具原定义）：
  1. 输入面要素类
  2. 分组字段（留空表示整体融合）
  3. 输出点要素类

用法：
    python run.py <输入面要素类> <分组字段（留空表示整体融合）> <输出点要素类>
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
    if len(argv) < 3:
        print(u"用法: python run.py <输入面要素类> <分组字段（留空表示整体融合）> <输出点要素类>")
        return 1
    in_polygons = argv[0]
    group_field = argv[1]
    out_points = argv[2]
    arcpy.env.overwriteOutput = True
    desc = arcpy.Describe(in_polygons)
    if desc.shapeType != 'Polygon':
        raise ValueError(u"输入必须是面要素类，当前是: %s" % desc.shapeType)

    tmp = arcpy.CreateUniqueName('diss', 'in_memory')
    grp = group_field if group_field else '#'
    arcpy.Dissolve_management(in_polygons, tmp, grp)
    arcpy.FeatureToPoint_management(tmp, out_points, 'CENTROID')
    arcpy.Delete_management(tmp)
    print(u"输出: %s，共 %s 个质心"
          % (out_points, arcpy.GetCount_management(out_points).getOutput(0)))
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
