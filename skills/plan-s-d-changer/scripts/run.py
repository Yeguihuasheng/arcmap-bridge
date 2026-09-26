# -*- coding: utf-8 -*-
"""
三调DLBM和DLMC转换（plan-s-d-changer）
模式 DLBM转DLMC：DLBM(编码) -> DLMC(名称)   [sheet1]
模式 DLMC转DLBM：DLMC(名称) -> DLBM(编码)   [sheet2]

用法（AI 问询后代入参数执行）：
    run.py <图层或要素类路径> <DLBM字段> <DLMC字段> <模式:DLBM转DLMC|DLMC转DLBM>
"""
import sys
import os
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C

HERE = C.skill_dir(u'plan-s-d-changer')
XLSX = os.path.join(HERE, u'resources', u'三调BM_MC.xlsx')


def main(fc, f_dlbm, f_dlmc, mode):
    if not arcpy.Exists(fc):
        C.log(u'错误：数据不存在 ' + fc)
        return 1
    if mode not in (u'DLBM转DLMC', u'DLMC转DLBM'):
        C.log(u'错误：模式必须是 DLBM转DLMC 或 DLMC转DLBM')
        return 2

    if mode == u'DLBM转DLMC':
        src_field, dst_field, sheet = f_dlbm, f_dlmc, 0
    else:
        src_field, dst_field, sheet = f_dlmc, f_dlbm, 1

    if not C.field_exists(fc, src_field):
        C.log(u'错误：源字段不存在 ' + src_field)
        return 1
    C.ensure_field(fc, dst_field, u'TEXT', 60)

    mapping = C.read_xlsx_dict(XLSX, sheet_index=sheet, key_col=0, val_col=1)
    C.log(u'读入映射 %d 条（模式 %s）' % (len(mapping), mode))

    hit = 0
    miss = 0
    with arcpy.da.UpdateCursor(fc, [src_field, dst_field]) as cur:
        for src, _ in cur:
            key = (src if isinstance(src, unicode) else C.S(src)).strip() if src is not None else u''
            if key in mapping:
                cur.updateRow([src, mapping[key]])
                hit += 1
            else:
                miss += 1
    n = int(arcpy.GetCount_management(fc).getOutput(0))
    C.log(u'完成：%d 条要素，命中 %d，未命中 %d' % (n, hit, miss))
    if miss:
        C.log(u'  （未命中 %d 条，字段值保留原样）' % miss)
    # 复核抽样
    with arcpy.da.SearchCursor(fc, [src_field, dst_field]) as cur:
        cnt = 0
        for s, d in cur:
            C.log(u'  抽样 %s -> %s' % (C.S(s), C.S(d)))
            cnt += 1
            if cnt >= 3:
                break
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 5:
        C.log(u'用法: run.py <图层> <DLBM字段> <DLMC字段> <模式>')
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]))
