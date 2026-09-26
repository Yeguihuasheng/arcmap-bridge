# -*- coding: utf-8 -*-
"""
三调转用地用海（plan-s-d2-y-d-y-h）
三调地类名称(DLMC) -> 用地用海名称(目标字段)。
转换类型三选一（对应映射表 3 个 sheet）：
  通用 -> sheet「通用」；待细分转一级类 -> sheet「待细分转一级类」；全部转一级类 -> sheet「全部转一级类」
版本：旧版(三调用地名称_to_用地用海用地名称.xlsx) / 新版(..._新版.xlsx)

用法：
    run.py <图层> <三调名称字段DLMC> <目标字段> <转换类型> <版本>
"""
import sys
import os
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C

RES = C.skill_dir(u'plan-s-d2-y-d-y-h') + u'\\resources'

SHEET_BY_TYPE = {u'通用': u'通用', u'待细分转一级类': u'待细分转一级类', u'全部转一级类': u'全部转一级类'}


def main(fc, f_dlmc, f_target, conv_type, version):
    if not arcpy.Exists(fc):
        C.log(u'错误：数据不存在 ' + fc)
        return 1
    if conv_type not in SHEET_BY_TYPE:
        C.log(u'错误：转换类型必须是 通用/待细分转一级类/全部转一级类')
        return 2
    if not C.field_exists(fc, f_dlmc):
        C.log(u'错误：三调名称字段不存在 ' + f_dlmc)
        return 1
    C.ensure_field(fc, f_target, u'TEXT', 60)

    fname = (u'三调用地名称_to_用地用海用地名称_新版.xlsx' if version == u'新版'
             else u'三调用地名称_to_用地用海用地名称.xlsx')
    xlsx = os.path.join(RES, fname)
    # 找目标 sheet 的索引
    names = C.read_xlsx_sheet_names(xlsx)
    target_sheet = SHEET_BY_TYPE[conv_type]
    if target_sheet not in names:
        C.log(u'错误：映射表缺少 sheet「%s」，现有 %s' % (target_sheet, names))
        return 1
    si = names.index(target_sheet)
    mapping = C.read_xlsx_dict(xlsx, si, 0, 1)
    C.log(u'读入映射 %d 条（%s / %s）' % (len(mapping), conv_type, version))

    hit = miss = 0
    with arcpy.da.UpdateCursor(fc, [f_dlmc, f_target]) as cur:
        for src, _ in cur:
            key = (src if isinstance(src, unicode) else C.S(src)).strip() if src is not None else u''
            if key in mapping:
                cur.updateRow([src, mapping[key]])
                hit += 1
            else:
                miss += 1
    n = int(arcpy.GetCount_management(fc).getOutput(0))
    C.log(u'完成：%d 条，命中 %d，未命中 %d' % (n, hit, miss))
    with arcpy.da.SearchCursor(fc, [f_dlmc, f_target]) as cur:
        cnt = 0
        for s, d in cur:
            C.log(u'  抽样 %s -> %s' % (C.S(s), C.S(d)))
            cnt += 1
            if cnt >= 3:
                break
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 6:
        C.log(u'用法: run.py <图层> <三调名称字段> <目标字段> <转换类型> <版本>')
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]))
