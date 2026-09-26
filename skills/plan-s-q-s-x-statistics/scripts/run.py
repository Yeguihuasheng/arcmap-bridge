# -*- coding: utf-8 -*-
"""
三线占用情况汇总表（plan-s-q-s-x-statistics）
开发边界/永基农田/生态红线 三个图层分别与分区做 Clip+Identity，
按分区统计占用面积（永基农田可乘扣减系数），输出三区三线指标汇总表。

用法：
    run.py <分区图层> <分区名字段> <开发边界图层> <永基农田图层> <生态红线图层> <面积类型> <单位> <输出CSV> [永基农田扣减系数字段]
"""
import sys
import os
import csv
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C


def _stat(line_fc, zone_fc, zone_field, area_type, kc_field=None):
    """单条线图层 vs 分区 -> {分区名: 面积}。"""
    d = {}
    inter = u'in_memory/inter_sx'
    if arcpy.Exists(inter):
        arcpy.Delete_management(inter)
    arcpy.Identity_analysis(line_fc, zone_fc, inter)
    if not C.field_exists(inter, u'mj_sx'):
        arcpy.AddField_management(inter, u'mj_sx', u'DOUBLE')
    # 面积（永基农田乘扣减系数）
    if kc_field and C.field_exists(inter, kc_field):
        arcpy.CalculateField_management(inter, u'mj_sx', u'%s*(1-!%s!)' % (C.area_expr(area_type, inter), kc_field), u'PYTHON')
    else:
        arcpy.CalculateField_management(inter, u'mj_sx', C.area_expr(area_type, inter), u'PYTHON')
    with arcpy.da.SearchCursor(inter, [zone_field, u'mj_sx']) as cur:
        for zv, a in cur:
            key = C.S(zv) if zv is not None else u''
            d[key] = d.get(key, 0.0) + (float(a) if a is not None else 0.0)
    arcpy.Delete_management(inter)
    return d


def main(zone_fc, zone_field, kf_fc, yj_fc, st_fc, area_type, unit, out_csv, kc_field=None):
    if not arcpy.Exists(zone_fc):
        C.log(u'错误：分区图层不存在 ' + zone_fc)
        return 1
    factor = C.unit_factor(unit)

    d_kf = _stat(kf_fc, zone_fc, zone_field, area_type)
    d_yj = _stat(yj_fc, zone_fc, zone_field, area_type, kc_field)
    d_st = _stat(st_fc, zone_fc, zone_field, area_type)

    all_zones = sorted(set(list(d_kf.keys()) + list(d_yj.keys()) + list(d_st.keys())))
    out_dir = os.path.dirname(out_csv)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(out_csv, 'wb') as f:
        f.write(u'\ufeff'.encode('utf-8'))
        w = C.UnicodeCsvWriter(f)
        w.writerow([u'分区', u'开发边界(%s)' % unit, u'永久基本农田(%s)' % unit, u'生态红线(%s)' % unit])
        for z in all_zones:
            w.writerow([z.encode('utf-8'), round(d_kf.get(z, 0.0) / factor, 4),
                        round(d_yj.get(z, 0.0) / factor, 4), round(d_st.get(z, 0.0) / factor, 4)])

    C.log(u'完成：%d 个分区，已输出 %s' % (len(all_zones), out_csv))
    for z in all_zones:
        C.log(u'  分区 %s: 开发边界 %.2f / 永基农田 %.2f / 生态红线 %.2f %s' %
              (z, d_kf.get(z, 0.0) / factor, d_yj.get(z, 0.0) / factor, d_st.get(z, 0.0) / factor, unit))
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 9:
        C.log(u'用法: run.py <分区图层> <分区字段> <开发边界> <永基农田> <生态红线> <面积类型> <单位> <输出CSV> [扣减系数字段]')
        sys.exit(2)
    kc = sys.argv[9] if len(sys.argv) > 9 else None
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7], sys.argv[8], kc))
