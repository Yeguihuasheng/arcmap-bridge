# -*- coding: utf-8 -*-
"""
按空间位置编号 —— ArcMap 版

按要素的空间位置（自上而下 / 自下而上 / 自左而右 等 8 种排序）给点要素类编号并写入新字段，图面编号、出图注记排序常用。

参数顺序（按地理处理工具原定义）：
  1. 输入点要素类
  2. 排序方式（默认 top_left）
  3. 编号字段名（默认 NUM）

用法：
    python run.py <输入点要素类> <排序方式（默认 top_left）> <编号字段名（默认 NUM）>
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
        print(u"用法: python run.py <输入点要素类> <排序方式（默认 top_left）> <编号字段名（默认 NUM）>")
        return 1
    in_points = argv[0]
    sort_by = argv[1]
    field_name = argv[2]
    keys = {
        'top_left': lambda r: (-r[2], r[1]),
        'top_right': lambda r: (-r[2], -r[1]),
        'bottom_left': lambda r: (r[2], r[1]),
        'bottom_right': lambda r: (r[2], -r[1]),
        'right_top': lambda r: (-r[1], -r[2]),
        'right_bottom': lambda r: (-r[1], r[2]),
        'left_top': lambda r: (r[1], -r[2]),
        'left_bottom': lambda r: (r[1], r[2]),
    }
    if sort_by not in keys:
        raise ValueError(u"未知的排序方式: %s（可选 %s）"
                         % (sort_by, u" / ".join(sorted(keys.keys()))))

    desc = arcpy.Describe(in_points)
    if desc.shapeType != 'Point':
        raise ValueError(u"该技能只支持点要素类，当前是: %s" % desc.shapeType)

    rows = list(arcpy.da.SearchCursor(in_points, ['OID@', 'SHAPE@X', 'SHAPE@Y']))
    rows.sort(key=keys[sort_by])
    mapping = {}
    for i, r in enumerate(rows):
        mapping[r[0]] = i + 1

    if field_name not in [f.name for f in arcpy.ListFields(in_points)]:
        arcpy.AddField_management(in_points, field_name, 'SHORT')

    with arcpy.da.UpdateCursor(in_points, ['OID@', field_name]) as cursor:
        for row in cursor:
            row[1] = mapping[row[0]]
            cursor.updateRow(row)
    print(u"已写入字段 %s，共 %d 个要素" % (field_name, len(rows)))
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
