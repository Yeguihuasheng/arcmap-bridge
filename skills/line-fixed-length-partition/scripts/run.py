# -*- coding: utf-8 -*-
"""
线按固定长度打断 —— ArcMap 版

把线要素按指定长度切成一段段等长的线（最后一段为剩余长度），保留原属性字段，常用于道路/管线分段、采样分段、里程统计。

参数顺序（按地理处理工具原定义）：
  1. 输入线要素类
  2. 输出工作空间
  3. 输出要素类名
  4. 分段长度
  5. 长度单位（METERS / FEET，默认 METERS）

用法：
    python run.py <输入线要素类> <输出工作空间> <输出要素类名> <分段长度> <长度单位（METERS / FEET，默认 METERS）>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import math
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
    if len(argv) < 5:
        print(u"用法: python run.py <输入线要素类> <输出工作空间> <输出要素类名> <分段长度> <长度单位（METERS / FEET，默认 METERS）>")
        return 1
    in_lines = argv[0]
    workspace = argv[1]
    out_name = argv[2]
    seg_length = float(argv[3])
    units = argv[4]
    arcpy.env.overwriteOutput = True
    if units not in ('METERS', 'FEET'):
        raise ValueError(u"units 必须是 METERS 或 FEET")
    if seg_length <= 0:
        raise ValueError(u"分段长度必须大于 0")

    sr = arcpy.Describe(in_lines).spatialReference
    out_mem = r'in_memory\out_part'
    arcpy.CreateFeatureclass_management('in_memory', 'out_part', 'POLYLINE',
                                        template=in_lines, spatial_reference=sr)
    names = [f.name for f in arcpy.ListFields(in_lines)]
    if 'SHAPE' in names:
        names.remove('SHAPE')
    fields = ['SHAPE@'] + names

    total = 0
    with arcpy.da.SearchCursor(in_lines, fields) as scur:
        with arcpy.da.InsertCursor(out_mem, fields) as icur:
            for srow in scur:
                line = srow[0]
                if line is None:
                    continue
                full_len = line.getLength('PLANAR', units)
                if not full_len or full_len <= 0:
                    continue
                parts = int(math.ceil(full_len / seg_length))
                start = 0.0
                end = seg_length
                for _i in range(parts + 1):
                    stop = full_len if end > full_len else end
                    seg = line.segmentAlongLine(start, stop)
                    if seg is not None and seg.length > 0:
                        icur.insertRow([seg] + list(srow[1:]))
                        total += 1
                    start = end
                    end = end + seg_length
                    if start >= full_len:
                        break

    out_path = os.path.join(workspace, out_name)
    arcpy.CopyFeatures_management(out_mem, out_path)
    arcpy.Delete_management(out_mem)
    print(u"输出: %s，共 %d 段" % (out_path, total))
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
