# -*- coding: utf-8 -*-
"""
生成分级用地用海编码名称（plan-create-grad-y-d-y-h）
从完整用地用海编码派生大/中/小类分级编码与名称字段。
- model: 分级数 1~3（1=大类前2位, 2=中类前4位, 3=小类前6位）
- 版本: 旧版(用地用海_DM_to_MC.xlsx) / 新版(新版用地用海_DM_to_MC.xlsx)
- isMC: 是否同时生成名称字段（MC_1/MC_2/MC_3）

用法：
    run.py <图层> <编码字段BM> <分级数1|2|3> <版本:旧版|新版> <是否生成名称:是|否>
"""
import sys
import os
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C

RES = C.skill_dir(u'plan-create-grad-y-d-y-h') + u'\\resources'


def main(fc, bm_field, model, version, is_mc):
    model = int(model)
    if model not in (1, 2, 3):
        C.log(u'错误：分级数必须是 1/2/3')
        return 2
    if not arcpy.Exists(fc):
        C.log(u'错误：数据不存在 ' + fc)
        return 1
    if not C.field_exists(fc, bm_field):
        C.log(u'错误：编码字段不存在 ' + bm_field)
        return 1

    xlsx = os.path.join(RES, (u'新版用地用海_DM_to_MC.xlsx' if version == u'新版'
                              else u'用地用海_DM_to_MC.xlsx'))
    mapping = C.read_xlsx_dict(xlsx, sheet_index=0, key_col=0, val_col=1) if is_mc == u'是' else {}

    bm_fields = [None, u'BM_1', u'BM_2', u'BM_3']
    mc_fields = [None, u'MC_1', u'MC_2', u'MC_3']
    cuts = [None, 2, 4, 6]

    for lv in range(1, model + 1):
        bmf = C.ensure_field(fc, bm_fields[lv], u'TEXT', 10)
        cut = cuts[lv]
        # 分级编码：截前 cut 位（长度不足则置空）
        codeblock = u"""
def cut(a):
    if a is None:
        return ''
    a = str(a)
    return a[:%d] if len(a) >= %d else ''
""" % (cut, cut)
        arcpy.CalculateField_management(fc, bmf, u'cut(!%s!)' % bm_field, u'PYTHON', codeblock)

        if is_mc == u'是' and mapping:
            mcf = C.ensure_field(fc, mc_fields[lv], u'TEXT', 60)
            with arcpy.da.UpdateCursor(fc, [bmf, mcf]) as cur:
                for bm, _ in cur:
                    key = (bm if isinstance(bm, unicode) else C.S(bm)).strip() if bm else u''
                    cur.updateRow([bm, mapping.get(key, u'')])
    n = int(arcpy.GetCount_management(fc).getOutput(0))
    C.log(u'完成：%d 条要素，生成分级字段 BM_1..BM_%d%s' %
          (n, model, (u' + MC_1..MC_%d' % model if is_mc == u'是' and mapping else u'')))
    # 复核抽样
    fields = [bm_field] + [bm_fields[i] for i in range(1, model + 1)]
    if is_mc == u'是' and mapping:
        fields += [mc_fields[i] for i in range(1, model + 1)]
    with arcpy.da.SearchCursor(fc, fields) as cur:
        cnt = 0
        for row in cur:
            C.log(u'  抽样 ' + u' | '.join([C.S(x) for x in row]))
            cnt += 1
            if cnt >= 3:
                break
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 6:
        C.log(u'用法: run.py <图层> <编码字段> <分级数> <版本> <是否生成名称>')
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]))
