# -*- coding: utf-8 -*-
"""
统计道路网密度（plan-statistic-load）
范围内道路 Clip -> 按道路类型求长度和 -> 路网密度(km/km²)。

用法：
    run.py <道路线图层> <道路类型字段> <范围面图层> <输出CSV>
"""
import sys
import os
import csv
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C

# 道路类型排序（铁路→高速→快速→主干→次干→支路→其它）
ROAD_ORDER = [u'铁路', u'高速公路', u'快速路', u'主干路', u'次干路', u'支路', u'其它']


def main(road_fc, road_type_field, range_fc, out_csv):
    if not arcpy.Exists(road_fc):
        C.log(u'错误：道路图层不存在 ' + road_fc)
        return 1
    if not arcpy.Exists(range_fc):
        C.log(u'错误：范围图层不存在 ' + range_fc)
        return 1
    if not C.field_exists(road_fc, road_type_field):
        C.log(u'错误：道路类型字段不存在 ' + road_type_field)
        return 1

    # Clip 范围内道路
    clip = u'in_memory/road_clip'
    if arcpy.Exists(clip):
        arcpy.Delete_management(clip)
    arcpy.Clip_analysis(road_fc, range_fc, clip)

    # 长度字段
    len_field = u'Shape_Length'
    if not C.field_exists(clip, len_field):
        arcpy.AddField_management(clip, len_field, u'DOUBLE')
        arcpy.CalculateField_management(clip, len_field, C.length_expr(clip), u'PYTHON')
    else:
        # 地理坐标系下 Shape_Length 是度，需重算为米
        if C.is_geographic(clip):
            arcpy.CalculateField_management(clip, len_field, C.length_expr(clip), u'PYTHON')

    # 按类型求长度和
    agg = {}
    with arcpy.da.SearchCursor(clip, [road_type_field, len_field]) as cur:
        for tv, ln in cur:
            key = C.S(tv) if tv is not None else u'其它'
            agg[key] = agg.get(key, 0.0) + (float(ln) if ln is not None else 0.0)

    # 范围面积（平方千米；地理坐标系用测地面积）
    area_km2 = 0.0
    if C.is_geographic(range_fc):
        for (a,) in arcpy.da.SearchCursor(range_fc, [u'SHAPE@AREA']):
            area_km2 += (float(a) if a is not None else 0.0) / 1e6
    else:
        with arcpy.da.SearchCursor(range_fc, [u'Shape_Area']) as cur:
            for (a,) in cur:
                area_km2 += (float(a) if a is not None else 0.0) / 1e6

    # 排序输出
    def order_key(t):
        if t in ROAD_ORDER:
            return ROAD_ORDER.index(t)
        return len(ROAD_ORDER)

    ordered = sorted(agg.keys(), key=order_key)
    out_dir = os.path.dirname(out_csv)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(out_csv, 'wb') as f:
        f.write(u'\ufeff'.encode('utf-8'))
        w = C.UnicodeCsvWriter(f)
        w.writerow([u'序号', u'类型', u'长度(km)', u'路网密度(km/km²)'])
        total_len = 0.0
        for i, t in enumerate(ordered, 1):
            km = agg[t] / 1000.0
            total_len += km
            density = (km / area_km2) if area_km2 else 0.0
            w.writerow([i, t.encode('utf-8'), round(km, 3), round(density, 4)])
        w.writerow([u'', u'合计', round(total_len, 3), round(total_len / area_km2, 4) if area_km2 else 0.0])

    C.log(u'完成：%d 种道路类型，总长 %.3f km，范围面积 %.2f km²，已输出 %s' %
          (len(ordered), sum(agg.values()) / 1000.0, area_km2, out_csv))
    for t in ordered:
        C.log(u'  %s: %.3f km' % (t, agg[t] / 1000.0))
    arcpy.Delete_management(clip)
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 5:
        C.log(u'用法: run.py <道路线图层> <道路类型字段> <范围面图层> <输出CSV>')
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]))
