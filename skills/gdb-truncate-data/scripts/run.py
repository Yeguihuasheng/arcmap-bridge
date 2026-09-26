# -*- coding: utf-8 -*-
"""
清空GDB要素数据（gdb-truncate-data）
清空 GDB 中要素数据、只保留字段结构（可用作新项目入库初始化）。
⚠️ 破坏性操作：执行前必须二次确认。

用法：
    run.py <GDB路径> [是否含独立要素类:是|否]
"""
import sys
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C


def main(gdb, include_standalone=u'否'):
    if not arcpy.Exists(gdb):
        C.log(u'错误：GDB 不存在 ' + gdb)
        return 1
    arcpy.env.workspace = gdb
    cleared = []

    # 1. 要素数据集内的要素类
    for fd in arcpy.ListDatasets(feature_type='Feature'):
        for fc in arcpy.ListFeatureClasses('', 'All', fd):
            path = gdb + u'\\' + fd + u'\\' + fc
            arcpy.TruncateTable_management(path)
            cleared.append(fd + u'/' + fc)

    # 2. 独立要素类（用户确认后）
    if include_standalone == u'是':
        for fc in arcpy.ListFeatureClasses():
            arcpy.TruncateTable_management(gdb + u'\\' + fc)
            cleared.append(fc)

    C.log(u'完成：已清空 %d 个要素类的数据（保留字段结构）' % len(cleared))
    for c in cleared:
        C.log(u'  ' + c)
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        C.log(u'用法: run.py <GDB路径> [是否含独立要素类:是|否]')
        sys.exit(2)
    inc = sys.argv[2] if len(sys.argv) > 2 else u'否'
    sys.exit(main(sys.argv[1], inc))
