# -*- coding: utf-8 -*-
"""
按长度创建路径（Route） —— ArcMap 版

把线要素按线长生成带量测值 M 的路由要素类，同一路径标识的线合并为一条路由，是线性参考分析的第一步。

参数顺序（按地理处理工具原定义）：
  1. 输入线要素
  2. 路径标识字段
  3. 输出路径要素类

用法：
    python run.py <输入线要素> <路径标识字段> <输出路径要素类>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import arcpy


def get_field(dataset, field_name):
    """取数据集里指定名称的字段对象"""
    for f in arcpy.Describe(dataset).fields:
        if f.name == field_name:
            return f
    raise ValueError(u"找不到字段: %s" % field_name)


def frange(start, stop, step):
    """支持浮点步长的 range"""
    r = start
    while r < stop:
        yield r
        if step > 0:
            r += step
        else:
            r -= step


def create_route_by_length(in_features, route_id_field, route_feature_class):
    """按线长度生成带量测值(M)的路由要素类。

    同一路径标识的线会被合并成一条路由；要求输入为单部件简单线，
    且同组线的数字化方向一致。
    """
    the_line = arcpy.CreateUniqueName('theLine', 'in_memory')
    arcpy.CopyFeatures_management(in_features, the_line)
    arcpy.AddField_management(the_line, 'FromMeasure', 'DOUBLE',
                              field_is_nullable='NULLABLE',
                              field_is_required='NON_REQUIRED')
    arcpy.AddField_management(the_line, 'ToMeasure', 'DOUBLE',
                              field_is_nullable='NULLABLE',
                              field_is_required='NON_REQUIRED')
    with arcpy.da.UpdateCursor(the_line, ['FromMeasure', 'ToMeasure',
                                          'SHAPE@LENGTH']) as cursor:
        for row in cursor:
            row[0] = 0
            row[1] = row[2]
            cursor.updateRow(row)

    arcpy.CreateRoutes_lr(the_line, route_id_field, route_feature_class,
                          'TWO_FIELDS', 'FromMeasure', 'ToMeasure')
    arcpy.Delete_management(the_line)
    return route_feature_class


def create_point_event_table(in_routes, route_id_field_name, measure_interval,
                             out_table):
    """按给定间隔生成点事件表（可直接喂给 Locate Features Along Routes）。"""
    fld = get_field(in_routes, route_id_field_name)
    path, name = os.path.split(out_table)
    arcpy.CreateTable_management(path, name)
    arcpy.AddField_management(out_table, route_id_field_name, fld.type,
                              field_length=fld.length)
    arcpy.AddField_management(out_table, 'Measure', 'DOUBLE')

    with arcpy.da.InsertCursor(out_table, [route_id_field_name, 'Measure']) as ic:
        with arcpy.da.SearchCursor(in_routes, [route_id_field_name,
                                               'SHAPE@']) as cursor:
            for row in cursor:
                line = row[1]
                first_measure = float(line.firstPoint.M)
                last_measure = float(line.lastPoint.M)
                for measure in frange(first_measure, last_measure,
                                      measure_interval):
                    ic.insertRow((row[0], measure))
    return out_table




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
        print(u"用法: python run.py <输入线要素> <路径标识字段> <输出路径要素类>")
        return 1
    in_features = argv[0]
    route_id_field = argv[1]
    out_route = argv[2]
    arcpy.env.overwriteOutput = True
    create_route_by_length(in_features, route_id_field, out_route)
    n = int(arcpy.GetCount_management(out_route).getOutput(0))
    print(u"输出路径要素类: %s" % out_route)
    print(u"生成路由 %d 条" % n)
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
