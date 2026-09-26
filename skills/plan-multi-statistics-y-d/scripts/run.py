# -*- coding: utf-8 -*-
"""
批量地类面积统计（plan-multi-statistics-y-d）
在 multi-statistics 基础上增加扣除系数：对每个待统计图层，用参照分区相交，
面积 = 原始面积 - 原始面积*扣除系数（BJMJ_EX），另算扣除面积（KCMJ_EX）。

用法：
    run.py <分区图层> <分区字段> <面积类型> <单位> <输出CSV> <图层> <扣除系数字段>
"""
import sys
import os
import csv
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C


def main(zone_fc, zone_field, area_type, unit, out_csv, layer, kc_field):
    if not arcpy.Exists(zone_fc):
        C.log(u'错误：分区图层不存在 ' + zone_fc)
        return 1
    if not arcpy.Exists(layer):
        C.log(u'错误：待统计图层不存在 ' + layer)
        return 1
    if not C.field_exists(zone_fc, zone_field):
        C.log(u'错误：分区字段不存在 ' + zone_field)
        return 1
    factor = C.unit_factor(unit)

    inter = u'in_memory/inter_kc'
    if arcpy.Exists(inter):
        arcpy.Delete_management(inter)
    arcpy.Intersect_analysis([layer, zone_fc], inter)
    if not C.field_exists(inter, u'BJMJ_OR'):
        arcpy.AddField_management(inter, u'BJMJ_OR', u'DOUBLE')
    if not C.field_exists(inter, u'BJMJ_EX'):
        arcpy.AddField_management(inter, u'BJMJ_EX', u'DOUBLE')
    if not C.field_exists(inter, u'KCMJ_EX'):
        arcpy.AddField_management(inter, u'KCMJ_EX', u'DOUBLE')
    arcpy.CalculateField_management(inter, u'BJMJ_OR', C.area_expr(area_type, inter), u'PYTHON')

    # 扣减系数（若图层有该字段则用，否则系数 0）
    if C.field_exists(inter, kc_field):
        arcpy.CalculateField_management(inter, u'BJMJ_EX', u'!BJMJ_OR! - !BJMJ_OR!*!%s!' % kc_field, u'PYTHON')
        arcpy.CalculateField_management(inter, u'KCMJ_EX', u'!BJMJ_OR!*!%s!' % kc_field, u'PYTHON')
    else:
        arcpy.CalculateField_management(inter, u'BJMJ_EX', u'!BJMJ_OR!', u'PYTHON')
        arcpy.CalculateField_management(inter, u'KCMJ_EX', u'0', u'PYTHON')

    agg = {}
    with arcpy.da.SearchCursor(inter, [zone_field, u'BJMJ_OR', u'BJMJ_EX', u'KCMJ_EX']) as cur:
        for zv, ori, ex, kc in cur:
            key = C.S(zv) if zv is not None else u''
            a = agg.get(key, [0.0, 0.0, 0.0])
            a[0] += float(ori) if ori is not None else 0.0
            a[1] += float(ex) if ex is not None else 0.0
            a[2] += float(kc) if kc is not None else 0.0
            agg[key] = a

    zones = sorted(agg)
    out_dir = os.path.dirname(out_csv)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(out_csv, 'wb') as f:
        f.write(u'\ufeff'.encode('utf-8'))
        w = C.UnicodeCsvWriter(f)
        w.writerow([u'分区'.encode('utf-8'), u'原始面积(%s)' % unit, u'扣除后面积(%s)' % unit, u'扣除面积(%s)' % unit])
        for z in zones:
            ori, ex, kc = agg[z]
            w.writerow([z.encode('utf-8'), round(ori / factor, 4), round(ex / factor, 4), round(kc / factor, 4)])

    C.log(u'完成：%d 个分区（扣除系数字段=%s），已输出 %s' % (len(zones), kc_field, out_csv))
    for z in zones:
        ori, ex, kc = agg[z]
        C.log(u'  分区 %s: 原始 %.2f, 扣除后 %.2f, 扣除 %.2f %s' % (z, ori / factor, ex / factor, kc / factor, unit))
    arcpy.Delete_management(inter)
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 8:
        C.log(u'用法: run.py <分区图层> <分区字段> <面积类型> <单位> <输出CSV> <图层> <扣除系数字段>')
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7]))
