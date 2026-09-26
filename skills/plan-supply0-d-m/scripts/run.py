# -*- coding: utf-8 -*-
"""
用地代码后补充0（plan-supply0-d-m）
语义：把用地代码用 0 右填充到指定位数 LEN（与 remove0 互为逆操作）。

用法（AI 问询 LEN 后代入参数执行）：
    run.py <图层或要素类路径> <字段名> <目标位数LEN>
"""
import sys
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C


def main(fc, field, length):
    try:
        length = int(length)
    except ValueError:
        C.log(u'错误：目标位数 LEN 必须是整数')
        return 2
    if not arcpy.Exists(fc):
        C.log(u'错误：数据不存在 ' + fc)
        return 1
    if not C.field_exists(fc, field):
        C.log(u'错误：字段不存在 ' + field)
        return 1
    # ljust 右填充（注意：只补到指定长度，超长不截断）
    expr = u'!%s!.ljust(%d, "0") if !%s! else ""' % (field, length, field)
    arcpy.CalculateField_management(fc, field, expr, u'PYTHON')
    n = int(arcpy.GetCount_management(fc).getOutput(0))
    C.log(u'完成：已对 %d 条要素的字段 [%s] 补0到 %d 位' % (n, field, length))
    with arcpy.da.SearchCursor(fc, [field]) as cur:
        cnt = 0
        for row in cur:
            C.log(u'  抽样 ' + C.S(row[0]))
            cnt += 1
            if cnt >= 3:
                break
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 4:
        C.log(u'用法: run.py <图层或要素类路径> <字段名> <目标位数LEN>')
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
