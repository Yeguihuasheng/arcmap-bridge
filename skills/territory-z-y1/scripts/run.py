# -*- coding: utf-8 -*-
"""
国土空间调查辅助·地类统计（territory-z-y1）
聚合国土辅助功能，mode 三选一：
  地类统计  ：按地类字段 Statistics 求面积和
  三大类归并：按 DLBM 前2位归并 农用地/建设用地/未利用地
  编码转换  ：DLBM 编码 -> 名称（三调BM_MC 查表）

用法：
    run.py <mode> <图层> <字段> <单位> <输出CSV> [面积字段]
"""
import sys
import os
import csv
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C

# 三大类归并（DLBM 前2位 -> 大类名）
DLBM_2 = {
    u'01': u'农用地', u'02': u'农用地', u'03': u'农用地', u'04': u'农用地',
    u'05': u'建设用地', u'06': u'建设用地', u'07': u'建设用地', u'08': u'建设用地',
    u'09': u'建设用地', u'10': u'建设用地',
    u'11': u'未利用地', u'12': u'未利用地',
}

XLSX = os.path.join(C.skill_dir(u'plan-s-d-changer'), u'resources', u'三调BM_MC.xlsx')


def _stat(fc, field, area_field, unit, out_csv):
    factor = C.unit_factor(unit)
    tem = u'in_memory/tem_zy'
    if arcpy.Exists(tem):
        arcpy.Delete_management(tem)
    arcpy.Statistics_analysis(fc, tem, u'%s SUM' % area_field, field)
    sfield = u'SUM_' + area_field
    d = {}
    with arcpy.da.SearchCursor(tem, [field, sfield]) as cur:
        for fv, a in cur:
            key = C.S(fv) if fv is not None else u''
            d[key] = d.get(key, 0.0) + (float(a) if a is not None else 0.0)
    _write_csv(out_csv, [u'地类', u'面积(%s)' % unit], [(k, round(v / factor, 4)) for k, v in sorted(d.items())], u'地类统计完成，%d 类' % len(d))


def _three_class(fc, field, area_field, unit, out_csv):
    factor = C.unit_factor(unit)
    d = {u'农用地': 0.0, u'建设用地': 0.0, u'未利用地': 0.0}
    with arcpy.da.SearchCursor(fc, [field, area_field]) as cur:
        for fv, a in cur:
            key = (C.S(fv) if fv is not None else u'')[:2]
            cls = DLBM_2.get(key, u'未利用地')
            d[cls] = d.get(cls, 0.0) + (float(a) if a is not None else 0.0)
    _write_csv(out_csv, [u'三大类', u'面积(%s)' % unit], [(k, round(v / factor, 4)) for k, v in sorted(d.items())], u'三大类归并完成')


def _code_to_name(fc, field, out_csv, area_field=None):
    mapping = C.read_xlsx_dict(XLSX, 0, 0, 1)
    d = {}
    with arcpy.da.SearchCursor(fc, [field]) as cur:
        for (fv,) in cur:
            key = (C.S(fv) if fv is not None else u'').strip()
            name = mapping.get(key, u'(未匹配)')
            d[name] = d.get(name, 0) + 1
    _write_csv(out_csv, [u'地类名称', u'图斑数'], [(k, v) for k, v in sorted(d.items())], u'编码转换完成，%d 类' % len(d))


def _write_csv(out_csv, header, rows, msg):
    out_dir = os.path.dirname(out_csv)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(out_csv, 'wb') as f:
        f.write(u'\ufeff'.encode('utf-8'))
        w = C.UnicodeCsvWriter(f)
        w.writerow([h.encode('utf-8') for h in header])
        for r in rows:
            w.writerow([(x.encode('utf-8') if isinstance(x, unicode) else x) for x in r])
    C.log(msg + u'，已输出 ' + out_csv)
    for r in rows:
        C.log(u'  ' + u' = '.join([C.S(x) for x in r]))


def main(mode, fc, field, unit, out_csv, area_field=None):
    if not arcpy.Exists(fc):
        C.log(u'错误：图层不存在 ' + fc)
        return 1
    if not C.field_exists(fc, field):
        C.log(u'错误：字段不存在 ' + field)
        return 1
    if mode == u'编码转换':
        return _code_to_name(fc, field, out_csv)
    # 需要面积字段
    if not area_field:
        area_field = u'Shape_Area'
    if not C.field_exists(fc, area_field):
        arcpy.AddField_management(fc, u'SDMJ', u'DOUBLE')
        arcpy.CalculateField_management(fc, u'SDMJ', C.area_expr(u'投影', fc), u'PYTHON')
        area_field = u'SDMJ'
    if mode == u'地类统计':
        return _stat(fc, field, area_field, unit, out_csv)
    if mode == u'三大类归并':
        return _three_class(fc, field, area_field, unit, out_csv)
    C.log(u'错误：mode 必须是 地类统计/三大类归并/编码转换')
    return 2


if __name__ == '__main__':
    if len(sys.argv) < 6:
        C.log(u'用法: run.py <mode> <图层> <字段> <单位> <输出CSV> [面积字段]')
        sys.exit(2)
    af = sys.argv[6] if len(sys.argv) > 6 else None
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], af))
