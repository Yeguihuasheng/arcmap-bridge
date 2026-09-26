# -*- coding: utf-8 -*-
"""
三调_统计三大类（plan-statistics-s-d-l）
对三调图层按 DLBM 归并到三大类（耕地/园地/林地/草地/其它/建设/未利用/农用地），
在分区（地块）图层上按三大类统计面积并写回字段（或输出 CSV）。

用法（zone 为空则只输出整体 CSV 汇总）：
    run.py <三调图层> <DLBM字段> <分区图层> <面积类型:投影|椭球> <单位> <输出CSV> [输出指标字段名逗号分隔]
"""
import sys
import os
import csv
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C


def main(sd_fc, dlbm_field, zone_fc, area_type, unit, out_csv, indicators=None):
    if not arcpy.Exists(sd_fc):
        C.log(u'错误：三调图层不存在 ' + sd_fc)
        return 1
    if not C.field_exists(sd_fc, dlbm_field):
        C.log(u'错误：DLBM 字段不存在 ' + dlbm_field)
        return 1
    factor = C.unit_factor(unit)

    # 选定的指标（默认全部 8 类）
    if indicators:
        inds = [x.strip() for x in indicators.split(u',') if x.strip() in C.SD_SQL]
    else:
        inds = [u'GDMJ', u'YDMJ', u'LDMJ', u'CDMJ', u'QTYDMJ', u'JSYDMJ', u'WLYDMJ', u'NYDMJ']

    # 若给了分区图层，用 Identity 把三调地块打上分区标识；否则整体统计
    if zone_fc and arcpy.Exists(zone_fc):
        # 用 SFID 字段承载分区 OID
        oid_field = [f.name for f in arcpy.ListFields(zone_fc) if f.type == u'OID'][0]
        sfid = u'SFID'
        if C.field_exists(zone_fc, sfid):
            arcpy.DeleteField_management(zone_fc, sfid)
        arcpy.AddField_management(zone_fc, sfid, u'TEXT', 20)
        arcpy.CalculateField_management(zone_fc, sfid, u'!%s!' % oid_field, u'PYTHON')
        # Identity(三调, 分区)
        identity = u'in_memory/identity_sd'
        if arcpy.Exists(identity):
            arcpy.Delete_management(identity)
        arcpy.Identity_analysis(sd_fc, zone_fc, identity)
        target = identity
        # 计算图斑面积
        if not C.field_exists(target, u'SDMJ'):
            arcpy.AddField_management(target, u'SDMJ', u'DOUBLE')
        arcpy.CalculateField_management(target, u'SDMJ', C.area_expr(area_type, target), u'PYTHON')
        area_field = u'SDMJ'
    else:
        target = sd_fc
        sfid = None
        # 无分区时也统一算 SDMJ（地理坐标系下 Shape_Area 是平方度，不可用）
        if not C.field_exists(target, u'SDMJ'):
            arcpy.AddField_management(target, u'SDMJ', u'DOUBLE')
        arcpy.CalculateField_management(target, u'SDMJ', C.area_expr(area_type, target), u'PYTHON')
        area_field = u'SDMJ'

    # 三大类归并 + 面积累加
    results = {}
    fields = [sfid, dlbm_field, area_field] if sfid else [dlbm_field, area_field]
    with arcpy.da.SearchCursor(target, fields) as cur:
        for row in cur:
            if sfid:
                zid, dlbm, area = row[0], row[1], row[2]
            else:
                zid, dlbm, area = u'', row[0], row[1]
            code = C.sd_classify(dlbm)
            if code is None:
                continue
            key = (zid if zid is not None else u'', code)
            results[key] = results.get(key, 0.0) + (float(area) if area is not None else 0.0)

    # 输出 CSV
    out_dir = os.path.dirname(out_csv)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(out_csv, 'wb') as f:
        f.write(u'\ufeff'.encode('utf-8'))
        w = C.UnicodeCsvWriter(f)
        header = ([u'分区'] if sfid else []) + [C.SD_ALIAS[i] for i in inds]
        w.writerow([h.encode('utf-8') for h in header])
        zones = sorted(set(k[0] for k in results)) if sfid else [u'']
        for z in zones:
            line = []
            if sfid:
                line.append((C.S(z) if isinstance(z, unicode) else C.S(z)).encode('utf-8'))
            for i in inds:
                v = results.get((z, i), 0.0) / factor
                line.append(round(v, 4))
            w.writerow(line)

    C.log(u'完成：归并到 %d 个分区 × %d 类，已输出 %s' % (len(zones), len(inds), out_csv))
    for z in zones:
        for i in inds:
            v = results.get((z, i), 0.0) / factor
            if v > 0:
                C.log(u'  %s %s = %.4f %s' % ((z if z else u'整体'), C.SD_ALIAS[i], v, unit))
    # 清理
    if zone_fc:
        try:
            arcpy.DeleteField_management(zone_fc, sfid)
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 7:
        C.log(u'用法: run.py <三调图层> <DLBM字段> <分区图层|空> <面积类型> <单位> <输出CSV> [指标字段]')
        sys.exit(2)
    zone = sys.argv[3] if sys.argv[3] != u'空' else None
    inds = sys.argv[7] if len(sys.argv) > 7 else None
    sys.exit(main(sys.argv[1], sys.argv[2], zone, sys.argv[4], sys.argv[5], sys.argv[6], inds))
