# -*- coding: utf-8 -*-
"""
线转道路（plan-line-to-road）—— ArcMap 降级实现
⚠️ 说明：原版是 Pro SDK GeometryEngine 精确几何（线偏移/圆角/交叉口处理），
ArcMap py2.7 无法精确复现。本降级版用 Buffer 近似生成道路红线与路缘石线，
中心线直接复制原线。适合快速出图，精确断面请回 Pro 版执行。

用法（AI 问询红线宽度等参数后代入）：
    run.py <中心线图层> <红线宽度(米)> <路缘石内缩(米)> <输出GDB> <红线名> <路缘石线名> <中心线名>
"""
import sys
import os
import arcpy

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C


def main(line_fc, redline_width, curb_inset, out_gdb, redline_name, curb_name, center_name):
    if not arcpy.Exists(line_fc):
        C.log(u'错误：中心线图层不存在 ' + line_fc)
        return 1
    try:
        redline_width = float(redline_width)
        curb_inset = float(curb_inset)
    except ValueError:
        C.log(u'错误：宽度必须是数字')
        return 2
    if redline_width <= 0:
        C.log(u'错误：红线宽度必须大于 0')
        return 1

    if not arcpy.Exists(out_gdb):
        # 输出 gdb 不存在则尝试创建（若路径是 gdb）
        if u'.gdb' in out_gdb.lower():
            d = os.path.dirname(out_gdb)
            if not os.path.isdir(d):
                os.makedirs(d)
            arcpy.CreateFileGDB_management(d, os.path.basename(out_gdb))
        else:
            C.log(u'错误：输出 GDB 不存在 ' + out_gdb)
            return 1

    sr = arcpy.Describe(line_fc).spatialReference
    half = redline_width / 2.0
    curb_half = max(0.0, half - curb_inset)

    # 1. 中心线：直接复制
    center_path = out_gdb + u'\\' + center_name
    if arcpy.Exists(center_path):
        arcpy.Delete_management(center_path)
    arcpy.CopyFeatures_management(line_fc, center_path)

    # 2. 红线：buffer 多边形（近似红线范围）
    redline_path = out_gdb + u'\\' + redline_name
    if arcpy.Exists(redline_path):
        arcpy.Delete_management(redline_path)
    arcpy.Buffer_analysis(line_fc, redline_path, u'%f Meters' % half, u'FULL', u'FLAT')

    # 3. 路缘石线：buffer 边界线（内缩）
    curb_path = out_gdb + u'\\' + curb_name
    if arcpy.Exists(curb_path):
        arcpy.Delete_management(curb_path)
    if curb_half > 0:
        arcpy.Buffer_analysis(line_fc, curb_path, u'%f Meters' % curb_half, u'FULL', u'FLAT')

    n = int(arcpy.GetCount_management(line_fc).getOutput(0))
    C.log(u'完成：%d 条中心线 -> 红线=%s 路缘石线=%s 中心线=%s' % (n, redline_path, curb_path, center_path))
    C.log(u'⚠ 本结果为 Buffer 近似，精确断面/交叉口圆角请用 Pro 版')
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 8:
        C.log(u'用法: run.py <中心线> <红线宽度> <路缘石内缩> <输出GDB> <红线名> <路缘石线名> <中心线名>')
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7]))
