# -*- coding: utf-8 -*-
"""
智能汇总统计（plan-multi-statistics）
以分区图层为参照，对多个待统计图层做 Intersect 后按分区统计面积，输出智能统计表(CSV)。

用法：
    run.py <分区图层> <分区字段> <面积类型:投影|椭球> <单位> <输出CSV> <图层1> [图层2 ...]
"""
import sys
import os
import csv
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C


def main(zone_fc, zone_field, area_type, unit, out_csv, layers):
    # layers 兼容：单字符串包成列表
    if isinstance(layers, (str, unicode)):
        layers = [layers]
    if not arcpy.Exists(zone_fc):
        C.log(u'错误：分区图层不存在 ' + zone_fc)
        return 1
    if not C.field_exists(zone_fc, zone_field):
        C.log(u'错误：分区字段不存在 ' + zone_field)
        return 1
    factor = C.unit_factor(unit)

    # 汇总结构：{图层名: {分区值: 面积}}
    agg = {}
    order = []
    for ly in layers:
        if not arcpy.Exists(ly):
            C.log(u'跳过不存在的图层：%s' % ly)
            continue
        name = C.S(os.path.splitext(os.path.basename(ly))[0])
        order.append(name)
        d = {}
        inter = u'in_memory/inter_%s' % name
        if arcpy.Exists(inter):
            arcpy.Delete_management(inter)
        arcpy.Intersect_analysis([ly, zone_fc], inter)
        # 加 BJMJ 字段
        if not C.field_exists(inter, u'BJMJ'):
            arcpy.AddField_management(inter, u'BJMJ', u'DOUBLE')
        arcpy.CalculateField_management(inter, u'BJMJ', C.area_expr(area_type, inter), u'PYTHON')
        # 按分区字段统计
        with arcpy.da.SearchCursor(inter, [zone_field, u'BJMJ']) as cur:
            for zv, a in cur:
                key = C.S(zv) if zv is not None else u''
                d[key] = d.get(key, 0.0) + (float(a) if a is not None else 0.0)
        agg[name] = d
        arcpy.Delete_management(inter)

    # 所有分区值
    all_zones = sorted(set(z for d in agg.values() for z in d))

    out_dir = os.path.dirname(out_csv)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(out_csv, 'wb') as f:
        f.write(u'\ufeff'.encode('utf-8'))
        w = C.UnicodeCsvWriter(f)
        w.writerow([u'分区'.encode('utf-8')] + [n.encode('utf-8') for n in order])
        for z in all_zones:
            row = [z.encode('utf-8')]
            for n in order:
                row.append(round(agg[n].get(z, 0.0) / factor, 4))
            w.writerow(row)

    C.log(u'完成：%d 个图层 × %d 个分区，已输出 %s' % (len(order), len(all_zones), out_csv))
    for z in all_zones:
        C.log(u'  分区 %s: %s' % (z, u', '.join([u'%s=%.2f' % (n, agg[n].get(z, 0.0) / factor) for n in order])))
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 7:
        C.log(u'用法: run.py <分区图层> <分区字段> <面积类型> <单位> <输出CSV> <图层1> [图层2 ...]')
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6:]))
