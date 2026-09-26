# -*- coding: utf-8 -*-
"""
用地用海转换（plan-y-d-y-h-changer）
用地用海编码 <-> 名称 互转（作用于用地用海字段）。
model: 代码转名称 / 名称转代码
version: 旧版(用地用海_DM_to_MC.xlsx) / 新版(新版用地用海_DM_to_MC.xlsx)

用法：
    run.py <图层> <源字段before> <目标字段after> <模式:代码转名称|名称转代码> <版本:旧版|新版>
"""
import sys
import os
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C

RES = C.skill_dir(u'plan-y-d-y-h-changer') + u'\\resources'


def main(fc, f_before, f_after, model, version):
    if not arcpy.Exists(fc):
        C.log(u'错误：数据不存在 ' + fc)
        return 1
    if model not in (u'代码转名称', u'名称转代码'):
        C.log(u'错误：模式必须是 代码转名称 或 名称转代码')
        return 2
    if not C.field_exists(fc, f_before):
        C.log(u'错误：源字段不存在 ' + f_before)
        return 1
    C.ensure_field(fc, f_after, u'TEXT', 60)

    xlsx = os.path.join(RES, (u'新版用地用海_DM_to_MC.xlsx' if version == u'新版'
                              else u'用地用海_DM_to_MC.xlsx'))
    m = C.read_xlsx_dict(xlsx, 0, 0, 1)  # 代码 -> 名称
    if model == u'名称转代码':
        m = {v: k for k, v in m.items()}
    C.log(u'读入映射 %d 条（%s / %s）' % (len(m), model, version))

    hit = miss = 0
    with arcpy.da.UpdateCursor(fc, [f_before, f_after]) as cur:
        for src, _ in cur:
            key = (src if isinstance(src, unicode) else C.S(src)).strip() if src is not None else u''
            if key in m:
                cur.updateRow([src, m[key]])
                hit += 1
            else:
                cur.updateRow([src, u''])
                miss += 1
    n = int(arcpy.GetCount_management(fc).getOutput(0))
    C.log(u'完成：%d 条，命中 %d，未命中 %d（未命中写空）' % (n, hit, miss))
    with arcpy.da.SearchCursor(fc, [f_before, f_after]) as cur:
        cnt = 0
        for s, d in cur:
            C.log(u'  抽样 %s -> %s' % (C.S(s), C.S(d)))
            cnt += 1
            if cnt >= 3:
                break
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 6:
        C.log(u'用法: run.py <图层> <源字段> <目标字段> <模式> <版本>')
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]))
