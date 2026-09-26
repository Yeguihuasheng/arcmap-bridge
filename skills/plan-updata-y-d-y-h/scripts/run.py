# -*- coding: utf-8 -*-
"""
赋值用地用海编码和名称（plan-updata-y-d-y-h）
给指定要素批量写入指定用地用海分类的编码和名称。
输入一个「编码+名称」合并值（如 "01耕地"），自动拆成编码(01)与名称(耕地)
分别写入编码字段与名称字段。

用法（AI 问询用地用海类型合并值后代入）：
    run.py <图层> <编码字段> <名称字段> <用地用海合并值> [可选SQL筛选]
"""
import sys
import re
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C


def split_ydyh(combined):
    """拆「编码+名称」合并串 -> (编码, 名称)。名称=全部中文，编码=其余。"""
    mc = u''.join(re.findall(u'[\u4e00-\u9fff]', combined))
    bm = u''.join(ch for ch in combined if ch not in mc).strip()
    return bm, mc


def main(fc, f_bm, f_mc, combined, where=None):
    if not arcpy.Exists(fc):
        C.log(u'错误：数据不存在 ' + fc)
        return 1
    C.ensure_field(fc, f_bm, u'TEXT', 20)
    C.ensure_field(fc, f_mc, u'TEXT', 60)
    bm, mc = split_ydyh(combined)
    C.log(u'拆解：编码=[%s] 名称=[%s]' % (bm, mc))
    if not mc:
        C.log(u'错误：合并值里未识别到中文名称部分')
        return 2

    fields = [f_bm, f_mc]
    cursor = arcpy.da.UpdateCursor(fc, fields, where_clause=where) if where else arcpy.da.UpdateCursor(fc, fields)
    cnt = 0
    with cursor as cur:
        for _ in cur:
            cur.updateRow([bm, mc])
            cnt += 1
    C.log(u'完成：已为 %d 条要素赋值 编码=%s 名称=%s' % (cnt, bm, mc))
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 5:
        C.log(u'用法: run.py <图层> <编码字段> <名称字段> <用地用海合并值> [SQL筛选]')
        sys.exit(2)
    where = sys.argv[5] if len(sys.argv) > 5 else None
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], where))
