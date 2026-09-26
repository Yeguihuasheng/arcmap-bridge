# -*- coding: utf-8 -*-
"""
通用面积统计（plan-general-statistic）
按任意字段（1~N 个）分组统计面积与占比，输出统计表（CSV，utf-8-sig，Excel 可开）。

用法：
    run.py <图层> <面积字段> <分组字段(分号分隔)> <单位:平方米|公顷|平方公里|亩> <输出CSV路径> [小数位]
"""
import sys
import os
import csv
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C


def main(fc, area_field, stat_fields_str, unit, out_csv, digit='4'):
    if not arcpy.Exists(fc):
        C.log(u'错误：数据不存在 ' + fc)
        return 1
    stat_fields = [f.strip() for f in stat_fields_str.split(u';') if f.strip()]
    if not stat_fields:
        C.log(u'错误：分组字段为空')
        return 2
    for f in [area_field] + stat_fields:
        if not C.field_exists(fc, f):
            C.log(u'错误：字段不存在 ' + f)
            return 1
    factor = C.unit_factor(unit)
    try:
        digit = int(digit)
    except ValueError:
        digit = 4

    # Statistics 分组汇总
    tem_sta = u'in_memory/tem_sta'
    if arcpy.Exists(tem_sta):
        arcpy.Delete_management(tem_sta)
    stat_field_expr = u';'.join(stat_fields)
    arcpy.Statistics_analysis(fc, tem_sta, u'%s SUM' % area_field, stat_field_expr)

    sum_field = u'SUM_' + area_field
    # 总面积
    total = 0.0
    rows = []
    with arcpy.da.SearchCursor(tem_sta, stat_fields + [sum_field]) as cur:
        for row in cur:
            vals = [C.S(v) if v is not None else u'' for v in row[:-1]]
            area = float(row[-1]) if row[-1] is not None else 0.0
            total += area
            rows.append((vals, area))
    total_disp = total / factor

    # 写 CSV
    out_dir = os.path.dirname(out_csv)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(out_csv, 'wb') as f:
        f.write(u'\ufeff'.encode('utf-8'))  # BOM
        w = C.UnicodeCsvWriter(f)
        header = stat_fields + [u'用地面积(%s)' % unit, u'占比(%)']
        w.writerow([h.encode('utf-8') for h in header])
        for vals, area in rows:
            a = area / factor
            pct = (area / total * 100.0) if total else 0.0
            line = vals + [round(a, digit), round(pct, 2)]
            w.writerow([(C.S(x) if isinstance(x, unicode) else x).encode('utf-8') if isinstance(x, unicode) else x for x in line])
        # 总面积行
        w.writerow([u'总面积'.encode('utf-8')] + [b'' for _ in stat_fields[1:]] +
                   [round(total_disp, digit), 100.0])

    C.log(u'完成：%d 个分组，总面积 %.4f %s，已输出 %s' % (len(rows), total_disp, unit, out_csv))
    C.log(u'明细：')
    for vals, area in rows:
        C.log(u'  %s -> %.4f %s (%.2f%%)' % (u'/'.join(vals), area / factor, unit, (area / total * 100.0) if total else 0.0))
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 6:
        C.log(u'用法: run.py <图层> <面积字段> <分组字段;分隔> <单位> <输出CSV> [小数位]')
        sys.exit(2)
    d = sys.argv[6] if len(sys.argv) > 6 else '4'
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], d))
