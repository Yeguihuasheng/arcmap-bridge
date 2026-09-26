# -*- coding: utf-8 -*-
"""
生成道路交叉口（plan-create-road-intersection）—— ArcMap 降级实现
⚠️ 说明：原版是 Pro SDK 精确几何（交点打断 + 转弯半径圆角），ArcMap py2.7 无法精确复现。
本降级版用 Intersect 求道路中心线交点输出为交叉口点要素，近似定位交叉口位置。

用法：
    run.py <道路中心线图层> <输出GDB> <输出要素类名>
"""
import sys
import os
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C


def main(road_fc, out_gdb, out_name):
    if not arcpy.Exists(road_fc):
        C.log(u'错误：道路图层不存在 ' + road_fc)
        return 1
    if not arcpy.Exists(out_gdb):
        if u'.gdb' in out_gdb.lower():
            d = os.path.dirname(out_gdb)
            if not os.path.isdir(d):
                os.makedirs(d)
            arcpy.CreateFileGDB_management(d, os.path.basename(out_gdb))
        else:
            C.log(u'错误：输出 GDB 不存在 ' + out_gdb)
            return 1

    out_path = out_gdb + u'\\' + out_name
    if arcpy.Exists(out_path):
        arcpy.Delete_management(out_path)
    # 线自相交 -> 交点（输出点要素）
    arcpy.Intersect_analysis([road_fc], out_path, output_type=u'POINT')

    n = int(arcpy.GetCount_management(out_path).getOutput(0))
    C.log(u'完成：生成 %d 个道路交叉口点 -> %s' % (n, out_path))
    C.log(u'⚠ 本结果为交点近似，精确交叉口圆角/转弯半径请用 Pro 版')
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 4:
        C.log(u'用法: run.py <道路中心线图层> <输出GDB> <输出要素类名>')
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
