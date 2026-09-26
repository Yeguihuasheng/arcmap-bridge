# -*- coding: utf-8 -*-
"""
用地用海指标汇总（plan-statistics-y-d-y-h）
按用地用海编码逐级（大类前2位/中类前4位/小类前6位）汇总面积与占比。

用法：
    run.py <图层> <编码字段> <面积字段> <单位> <分级:大类|中类|小类> <输出CSV> [分区图层|空] [分区字段]
"""
import sys
import os
import csv
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C

CUT = {u'大类': 2, u'中类': 4, u'小类': 6}


def main(fc, bm_field, area_field, unit, level, out_csv, zone_fc=None, zone_field=None):
    if not arcpy.Exists(fc):
        C.log(u'错误：图层不存在 ' + fc)
        return 1
    if level not in CUT:
        C.log(u'错误：分级必须是大类/中类/小类')
        return 2
    if not C.field_exists(fc, bm_field):
        C.log(u'错误：编码字段不存在 ' + bm_field)
        return 1
    if not C.field_exists(fc, area_field):
        C.log(u'错误：面积字段不存在 ' + area_field)
        return 1
    cut = CUT[level]
    factor = C.unit_factor(unit)

    # 可选分区域：Clip 到分区
    if zone_fc and arcpy.Exists(zone_fc) and zone_field:
        # 逐分区统计
        results = {}
        with arcpy.da.SearchCursor(zone_fc, [zone_field]) as zcur:
            zones = []
            for (zv,) in zcur:
                if zv not in zones:
                    zones.append(zv)
        for zv in zones:
            where = u"%s = '%s'" % (zone_field, zv)
            sel = u'in_memory/zone_sel'
            if arcpy.Exists(sel):
                arcpy.Delete_management(sel)
            arcpy.Select_analysis(zone_fc, sel, where)
            clip = u'in_memory/clip_zone'
            if arcpy.Exists(clip):
                arcpy.Delete_management(clip)
            arcpy.Clip_analysis(fc, sel, clip)
            d = {}
            with arcpy.da.SearchCursor(clip, [bm_field, area_field]) as cur:
                for bm, a in cur:
                    key = (C.S(bm) if bm is not None else u'')[:cut]
                    d[key] = d.get(key, 0.0) + (float(a) if a is not None else 0.0)
            results[C.S(zv)] = d
            arcpy.Delete_management(sel)
            arcpy.Delete_management(clip)
        _write_zones(out_csv, level, results, factor, unit)
        C.log(u'完成：按分区统计，已输出 %s' % out_csv)
        return 0

    # 整体统计
    d = {}
    with arcpy.da.SearchCursor(fc, [bm_field, area_field]) as cur:
        for bm, a in cur:
            key = (C.S(bm) if bm is not None else u'')[:cut]
            d[key] = d.get(key, 0.0) + (float(a) if a is not None else 0.0)
    total = sum(d.values())

    out_dir = os.path.dirname(out_csv)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(out_csv, 'wb') as f:
        f.write(u'\ufeff'.encode('utf-8'))
        w = C.UnicodeCsvWriter(f)
        w.writerow([u'编码', u'用地面积(%s)' % unit, u'占比(%)'])
        for key in sorted(d):
            w.writerow([key.encode('utf-8'), round(d[key] / factor, 4), round(d[key] / total * 100.0, 2) if total else 0.0])
        w.writerow([u'合计', round(total / factor, 4), 100.0])
    C.log(u'完成：%s 共 %d 类，总面积 %.4f %s，已输出 %s' % (level, len(d), total / factor, unit, out_csv))
    for key in sorted(d):
        C.log(u'  %s: %.4f %s (%.2f%%)' % (key, d[key] / factor, unit, d[key] / total * 100.0 if total else 0.0))
    return 0


def _write_zones(out_csv, level, results, factor, unit):
    out_dir = os.path.dirname(out_csv)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    all_codes = sorted(set(c for d in results.values() for c in d))
    with open(out_csv, 'wb') as f:
        f.write(u'\ufeff'.encode('utf-8'))
        w = C.UnicodeCsvWriter(f)
        w.writerow([u'分区'] + [c.encode('utf-8') for c in all_codes] + [u'合计(%s)' % unit])
        for z in sorted(results):
            row = [z.encode('utf-8')]
            s = 0.0
            for c in all_codes:
                v = results[z].get(c, 0.0)
                s += v
                row.append(round(v / factor, 4))
            row.append(round(s / factor, 4))
            w.writerow(row)


if __name__ == '__main__':
    if len(sys.argv) < 7:
        C.log(u'用法: run.py <图层> <编码字段> <面积字段> <单位> <分级> <输出CSV> [分区图层] [分区字段]')
        sys.exit(2)
    zone_fc = sys.argv[7] if len(sys.argv) > 7 and sys.argv[7] != u'空' else None
    zone_field = sys.argv[8] if len(sys.argv) > 8 else None
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], zone_fc, zone_field))
