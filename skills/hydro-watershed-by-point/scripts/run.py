# -*- coding: utf-8 -*-
"""
逐点划分流域（自动吸附汇流点） —— ArcMap 版

对每个输入点：先在给定搜索半径内把点吸附到**汇流累积最大**的像元上（Snap Pour Point），再用 D8 流向栅格圈出该点的上游汇水范围，输出每个点一个流域面。可选用地类栅格统计每个流域内各地类的面积。用于水库/堰坝控制流域、排污口上游范围划分。

参数顺序（按地理处理工具原定义）：
  1. 输入点要素（出水口/堰坝位置）
  2. 点编号字段（必须是整数字段，值会写进流域面）
  3. 汇流累积栅格（hydro-flowdir-d8 的产物）
  4. D8 流向栅格（hydro-flowdir-d8 的产物）
  5. 吸附搜索半径（如 100 或 100 Meters）
  6. 地类栅格（可选，整型；填 # 跳过面积统计）
  7. 输出流域面要素

用法：
    python run.py <输入点要素（出水口/堰坝位置）> <点编号字段（必须是整数字段，值会写进流域面）> <汇流累积栅格（hydro-flowdir-d8 的产物）> <D8 流向栅格（hydro-flowdir-d8 的产物）> <吸附搜索半径（如 100 或 100 Meters）> <地类栅格（可选，整型；填 # 跳过面积统计）> <输出流域面要素>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import arcpy


def _u(v):
    if v is None:
        return u''
    if isinstance(v, bytes):
        for enc in (u'mbcs', u'utf-8', u'gbk', u'latin-1'):
            try:
                return v.decode(enc)
            except Exception:
                continue
        return v.decode(u'utf-8', u'replace')
    return u'%s' % v


def _split(text):
    t = (text or u'').strip()
    if not t or t == u'#':
        return []
    return [p.strip() for p in t.split(u';') if p.strip()]


def _has_field(ds, name):
    for f in arcpy.ListFields(ds):
        if f.name.upper() == name.upper():
            return True
    return False




# ------------------------------------------------------------------ 运行入口
def _to_unicode(s):
    """py2 下 sys.argv 是字节串，中文参数不解码会和 u"" 比较炸，入口统一转 unicode。"""
    if not isinstance(s, bytes):
        return s
    for enc in (u"mbcs", u"utf-8", u"gbk", u"latin-1"):
        try:
            return s.decode(enc)
        except Exception:
            continue
    return s.decode(u"utf-8", u"replace")


def main(argv):
    if len(argv) < 7:
        print(u"用法: python run.py <输入点要素（出水口/堰坝位置）> <点编号字段（必须是整数字段，值会写进流域面）> <汇流累积栅格（hydro-flowdir-d8 的产物）> <D8 流向栅格（hydro-flowdir-d8 的产物）> <吸附搜索半径（如 100 或 100 Meters）> <地类栅格（可选，整型；填 # 跳过面积统计）> <输出流域面要素>")
        return 1
    points = argv[0]
    id_field = argv[1]
    flow_acc = argv[2]
    flow_dir = argv[3]
    snap_dist = argv[4]
    landcover = argv[5]
    out_fc = argv[6]
    if arcpy.CheckExtension('spatial') != 'Available':
        raise RuntimeError(u"需要 Spatial Analyst 扩展许可")
    arcpy.CheckOutExtension('spatial')
    try:
        arcpy.env.overwriteOutput = True
        arcpy.env.extent = flow_acc
        arcpy.env.mask = flow_acc
        arcpy.env.snapRaster = flow_acc
        sgdb = arcpy.env.scratchGDB
        snap = os.path.join(sgdb, u'ws_snap_tmp')
        ws_ras = os.path.join(sgdb, u'ws_ras_tmp')

        snapped = arcpy.sa.SnapPourPoint(points, flow_acc, snap_dist, id_field)
        snapped.save(snap)
        ws = arcpy.sa.Watershed(flow_dir, snap, "Value")
        ws.save(ws_ras)
        arcpy.RasterToPolygon_conversion(ws_ras, out_fc, "NO_SIMPLIFY", "VALUE")
        arcpy.AddField_management(out_fc, "WS_ID", "LONG")
        arcpy.CalculateField_management(out_fc, "WS_ID", "!gridcode!",
                                        "PYTHON_9.3")

        lc = (landcover or u'').strip()
        if lc and lc != u'#':
            tab = os.path.join(sgdb, u'ws_lc_tmp')
            arcpy.sa.TabulateArea(ws_ras, "Value", lc, "Value", tab)
            tfields = [f.name for f in arcpy.ListFields(tab)
                       if f.name not in (u"Value", u"OBJECTID", u"OBJECTID_1")]
            if tfields:
                arcpy.JoinField_management(out_fc, "gridcode", tab, "Value",
                                           tfields)
            print(u"地类面积字段 %d 个已挂到流域面" % len(tfields))
            arcpy.Delete_management(tab)

        arcpy.Delete_management(snap)
        arcpy.Delete_management(ws_ras)
        cnt = arcpy.GetCount_management(out_fc).getOutput(0)
        print(u"流域 -> %s（%s 个，吸附半径 %s）" % (out_fc, cnt, snap_dist))
        if int(cnt) < int(arcpy.GetCount_management(points).getOutput(0)):
            print(u"提示: 流域数少于点数，说明有点吸附到了同一像元")
    finally:
        arcpy.CheckInExtension('spatial')
    print(u"完成")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main([_to_unicode(v) for v in sys.argv[1:]]))
    except Exception as e:
        try:
            print(u"ERROR: %s" % e)
        except Exception:
            pass
        raise
