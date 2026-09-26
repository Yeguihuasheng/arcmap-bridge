# -*- coding: utf-8 -*-
"""
检查现状规划用地变化（plan-check-y-d-change）
检测现状图层与规划图层之间指定字段的用地性质变化，输出变化明细。

算法：SymDiff 重叠检查 -> CopyFeatures 两输入 -> AlterField 重命名 ->
Identity(现状=target, 规划=identity) -> 加「变化」字段逐行比较 ->
Select(变化 IS NOT NULL) 输出变化图斑 -> 清理中间层。

用法：
    run.py <现状图层> <规划图层> <现状字段> <规划字段> <输出要素类路径>
"""
import sys
import os
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C

CHANGE_FIELD = u'变化'


def main(fc_xz, fc_gh, field_xz, field_gh, out_fc):
    if not arcpy.Exists(fc_xz):
        C.log(u'错误：现状图层不存在 ' + fc_xz)
        return 1
    if not arcpy.Exists(fc_gh):
        C.log(u'错误：规划图层不存在 ' + fc_gh)
        return 1
    for f, d in [(field_xz, fc_xz), (field_gh, fc_gh)]:
        if not C.field_exists(d, f):
            C.log(u'错误：字段 %s 不存在于 %s' % (f, d))
            return 1

    out_dir = os.path.dirname(out_fc)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    # 1. 重叠检查（SymDiff）
    symdiff = u'in_memory/symdiff'
    try:
        arcpy.SymDiff_analysis(fc_xz, fc_gh, symdiff, u'ALL')
        if int(arcpy.GetCount_management(symdiff).getOutput(0)) > 0:
            C.log(u'⚠ 提醒：2 个输入图层不完全重叠！')
        arcpy.Delete_management(symdiff)
    except Exception:
        pass

    # 2. 复制 + 重命名字段（中间层放 in_memory，避免 shapefile 路径问题）
    tem_xz = u'in_memory/tem_xz'
    tem_gh = u'in_memory/tem_gh'
    identity = u'in_memory/identity'
    for p in (tem_xz, tem_gh, identity):
        if arcpy.Exists(p):
            arcpy.Delete_management(p)
    arcpy.CopyFeatures_management(fc_xz, tem_xz)
    arcpy.CopyFeatures_management(fc_gh, tem_gh)
    xz_new = u'现状_' + field_xz
    gh_new = u'规划_' + field_gh
    arcpy.AlterField_management(tem_xz, field_xz, xz_new)
    arcpy.AlterField_management(tem_gh, field_gh, gh_new)

    # 3. Identity（现状为 target，规划做 identity）
    arcpy.Identity_analysis(tem_xz, tem_gh, identity)

    # 4. 加变化字段逐行比较
    C.ensure_field(identity, CHANGE_FIELD, u'TEXT', 200)
    cnt_change = 0
    with arcpy.da.UpdateCursor(identity, [xz_new, gh_new, CHANGE_FIELD]) as cur:
        for xz_v, gh_v, _ in cur:
            if xz_v is not None and gh_v is not None and C.S(xz_v) != C.S(gh_v):
                cur.updateRow([xz_v, gh_v, u'【%s】-->【%s】' % (xz_v, gh_v)])
                cnt_change += 1

    # 5. 提取变化图斑（先落到 in_memory，再复制到目标，避免 shapefile 路径歧义）
    arcpy.env.overwriteOutput = True
    sel = u'in_memory/sel_change'
    if arcpy.Exists(sel):
        arcpy.Delete_management(sel)
    arcpy.Select_analysis(identity, sel, u'%s IS NOT NULL' % CHANGE_FIELD)
    # 确定输出路径：普通文件夹 → 统一补 .shp 扩展名；GDB 内 → 原名
    _out = out_fc
    _ext = os.path.splitext(out_fc)[1].lower()
    if _ext == u'' and not arcpy.env.workspace and not out_fc.lower().endswith(u'.gdb'):
        # 输出到普通文件夹，补 .shp
        if os.path.isdir(os.path.dirname(out_fc)) or out_fc.count(u'\\') or out_fc.count(u'/'):
            _out = out_fc + u'.shp'
    if arcpy.Exists(_out):
        arcpy.Delete_management(_out)
    arcpy.CopyFeatures_management(sel, _out)

    # 6. 清理中间层
    for p in (identity, tem_xz, tem_gh, sel):
        try:
            arcpy.Delete_management(p)
        except Exception:
            pass

    n = int(arcpy.GetCount_management(_out).getOutput(0))
    C.log(u'完成：共发现 %d 个变化图斑，已输出到 %s' % (cnt_change, _out))
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 6:
        C.log(u'用法: run.py <现状图层> <规划图层> <现状字段> <规划字段> <输出要素类>')
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]))
