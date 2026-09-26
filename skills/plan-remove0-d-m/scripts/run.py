# -*- coding: utf-8 -*-
"""
移除用地代码后的0（plan-remove0-d-m）
语义：用地代码只保留 2 位大类 或 4 位中类主干，砍掉其后的补位 0。
注意：不是 rstrip('0')——长度 3 的 "100" 会得到 "10"（rstrip 会错成 "1"）。

用法（AI 问询后代入参数执行）：
    run.py <图层或要素类路径> <字段名>
"""
import sys
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C

CODEBLOCK = u"""
def ss(a):
    if a is None:
        return None
    a = str(a)
    if len(a) <= 2:
        return a
    if a[2:] == '0' * (len(a) - 2):
        return a[:2]
    elif len(a) >= 4 and a[4:] == '0' * (len(a) - 4):
        return a[:4]
    else:
        return a
"""


def main(fc, field):
    if not arcpy.Exists(fc):
        C.log(u'错误：数据不存在 ' + fc)
        return 1
    if not C.field_exists(fc, field):
        C.log(u'错误：字段不存在 ' + field)
        return 1
    expr = u'ss(!%s!)' % field
    arcpy.CalculateField_management(fc, field, expr, u'PYTHON', CODEBLOCK)
    n = int(arcpy.GetCount_management(fc).getOutput(0))
    C.log(u'完成：已对 %d 条要素的字段 [%s] 移除补位0' % (n, field))
    # 复核：抽样 3 条
    with arcpy.da.SearchCursor(fc, [field]) as cur:
        cnt = 0
        for row in cur:
            C.log(u'  抽样 ' + C.S(row[0]))
            cnt += 1
            if cnt >= 3:
                break
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3:
        C.log(u'用法: run.py <图层或要素类路径> <字段名>')
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
