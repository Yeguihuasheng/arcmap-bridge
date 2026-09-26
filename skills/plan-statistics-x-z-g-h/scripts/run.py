# -*- coding: utf-8 -*-
"""
用地用海现状规划指标汇总（plan-statistics-x-z-g-h）
现状图层与规划图层分别按用地用海编码分级汇总面积，双列对比输出。

用法：
    run.py <现状图层> <规划图层> <编码字段> <面积字段> <单位> <分级:大类|中类|小类> <输出CSV>
"""
import sys
import os
import csv
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C

CUT = {u'大类': 2, u'中类': 4, u'小类': 6}


def _sum(fc, bm_field, area_field, cut):
    d = {}
    with arcpy.da.SearchCursor(fc, [bm_field, area_field]) as cur:
        for bm, a in cur:
            key = (C.S(bm) if bm is not None else u'')[:cut]
            d[key] = d.get(key, 0.0) + (float(a) if a is not None else 0.0)
    return d


def main(xz_fc, gh_fc, bm_field, area_field, unit, level, out_csv):
    if not arcpy.Exists(xz_fc) or not arcpy.Exists(gh_fc):
        C.log(u'错误：现状/规划图层不存在')
        return 1
    if level not in CUT:
        C.log(u'错误：分级必须是大类/中类/小类')
        return 2
    cut = CUT[level]
    factor = C.unit_factor(unit)

    d_xz = _sum(xz_fc, bm_field, area_field, cut)
    d_gh = _sum(gh_fc, bm_field, area_field, cut)
    all_codes = sorted(set(list(d_xz.keys()) + list(d_gh.keys())))
    t_xz = sum(d_xz.values())
    t_gh = sum(d_gh.values())

    out_dir = os.path.dirname(out_csv)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(out_csv, 'wb') as f:
        f.write(u'\ufeff'.encode('utf-8'))
        w = C.UnicodeCsvWriter(f)
        w.writerow([u'编码', u'现状面积(%s)' % unit, u'现状占比(%)', u'规划面积(%s)' % unit, u'规划占比(%)'])
        for c in all_codes:
            a = d_xz.get(c, 0.0)
            b = d_gh.get(c, 0.0)
            w.writerow([c.encode('utf-8'), round(a / factor, 4), round(a / t_xz * 100.0, 2) if t_xz else 0.0,
                        round(b / factor, 4), round(b / t_gh * 100.0, 2) if t_gh else 0.0])
        w.writerow([u'合计', round(t_xz / factor, 4), 100.0, round(t_gh / factor, 4), 100.0])

    C.log(u'完成：%s 共 %d 类，现状 %.4f %s / 规划 %.4f %s，已输出 %s' %
          (level, len(all_codes), t_xz / factor, unit, t_gh / factor, unit, out_csv))
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 8:
        C.log(u'用法: run.py <现状图层> <规划图层> <编码字段> <面积字段> <单位> <分级> <输出CSV>')
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7]))
