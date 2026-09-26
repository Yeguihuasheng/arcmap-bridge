# -*- coding: utf-8 -*-
"""
用地用海旧转新（plan-y-d-y-h-old2-new）
旧用地用海编码 -> 新编码 -> 新名称（两步级联映射）。
第1步：旧编码 -> 新编码（旧用地用海编码_to_新用地用海编码.xlsx sheet1）
第2步：新编码 -> 新名称（新版用地用海_DM_to_MC.xlsx sheet1）

用法：
    run.py <图层> <旧编码字段oldBM> <新编码字段newBM> <新名称字段newMC>
"""
import sys
import os
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C

RES = C.skill_dir(u'plan-y-d-y-h-old2-new') + u'\\resources'
MAP1 = os.path.join(RES, u'旧用地用海编码_to_新用地用海编码.xlsx')
MAP2 = os.path.join(RES, u'新版用地用海_DM_to_MC.xlsx')


def main(fc, old_bm, new_bm, new_mc):
    if not arcpy.Exists(fc):
        C.log(u'错误：数据不存在 ' + fc)
        return 1
    if not C.field_exists(fc, old_bm):
        C.log(u'错误：旧编码字段不存在 ' + old_bm)
        return 1
    C.ensure_field(fc, new_bm, u'TEXT', 20)
    C.ensure_field(fc, new_mc, u'TEXT', 60)

    m1 = C.read_xlsx_dict(MAP1, 0, 0, 1)  # 旧编码 -> 新编码
    m2 = C.read_xlsx_dict(MAP2, 0, 0, 1)  # 新编码 -> 新名称
    C.log(u'读入映射：旧->新 %d 条，新->名称 %d 条' % (len(m1), len(m2)))

    hit1 = hit2 = miss = 0
    with arcpy.da.UpdateCursor(fc, [old_bm, new_bm, new_mc]) as cur:
        for oldv, _, _ in cur:
            key = (oldv if isinstance(oldv, unicode) else C.S(oldv)).strip() if oldv is not None else u''
            nb = m1.get(key, u'')
            nm = m2.get(nb, u'')
            if nb:
                hit1 += 1
            if nm:
                hit2 += 1
            else:
                miss += 1
            cur.updateRow([oldv, nb, nm])
    n = int(arcpy.GetCount_management(fc).getOutput(0))
    C.log(u'完成：%d 条，旧->新命中 %d，新->名称命中 %d，缺名称 %d' % (n, hit1, hit2, miss))
    with arcpy.da.SearchCursor(fc, [old_bm, new_bm, new_mc]) as cur:
        cnt = 0
        for o, nb, nm in cur:
            C.log(u'  抽样 %s -> %s -> %s' % (C.S(o), C.S(nb), C.S(nm)))
            cnt += 1
            if cnt >= 3:
                break
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 5:
        C.log(u'用法: run.py <图层> <旧编码字段> <新编码字段> <新名称字段>')
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]))
