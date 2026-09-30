# -*- coding: utf-8 -*-
"""
横断面测点按河道/滩地分类 —— ArcMap 版

给横断面测点（hydro-xs-points 的产物）打两个标记字段：落在河道面（含缓冲）内的 channel=1，落在滩地面（含缓冲）内的 floodplain=1。用于糙率分区赋值、过流面积分段统计。本技能**原地修改**输入点要素。

参数顺序（按地理处理工具原定义）：
  1. 横断面测点要素类（将被加字段并原地修改）
  2. 河道面要素类
  3. 滩地（floodplain）面要素类
  4. 河道/滩地面的缓冲距离（坐标系单位，容忍边界缝隙）

用法：
    python run.py <横断面测点要素类（将被加字段并原地修改）> <河道面要素类> <滩地（floodplain）面要素类> <河道/滩地面的缓冲距离（坐标系单位，容忍边界缝隙）>
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
    return [p.strip() for p in t.replace(u',', u';').split(u';') if p.strip()]


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
    if len(argv) < 4:
        print(u"用法: python run.py <横断面测点要素类（将被加字段并原地修改）> <河道面要素类> <滩地（floodplain）面要素类> <河道/滩地面的缓冲距离（坐标系单位，容忍边界缝隙）>")
        return 1
    xs_points = argv[0]
    channel_polygon = argv[1]
    floodplain_polygon = argv[2]
    buffer_distance = float(argv[3])
    arcpy.env.overwriteOutput = True
    for f in (u'channel', u'floodplain'):
        if not _has_field(xs_points, f):
            arcpy.AddField_management(xs_points, f, u'SHORT')
        arcpy.CalculateField_management(xs_points, f, u'0', u'PYTHON_9.3')

    ch_buf = r'in_memory\xs_ch_buf'
    fp_buf = r'in_memory\xs_fp_buf'
    arcpy.Buffer_analysis(channel_polygon, ch_buf, buffer_distance)
    arcpy.Buffer_analysis(floodplain_polygon, fp_buf, buffer_distance)

    arcpy.MakeFeatureLayer_management(xs_points, u'xs_lyr')
    arcpy.SelectLayerByLocation_management(u'xs_lyr', u'INTERSECT', fp_buf,
                                           u'', u'NEW_SELECTION')
    arcpy.CalculateField_management(u'xs_lyr', u'floodplain', u'1',
                                    u'PYTHON_9.3')
    arcpy.SelectLayerByLocation_management(u'xs_lyr', u'INTERSECT', ch_buf,
                                           u'', u'NEW_SELECTION')
    arcpy.CalculateField_management(u'xs_lyr', u'channel', u'1',
                                    u'PYTHON_9.3')
    arcpy.SelectLayerByAttribute_management(u'xs_lyr', u'CLEAR_SELECTION')
    for t in (ch_buf, fp_buf):
        arcpy.Delete_management(t)
    print(u"分类完成: %s（channel/floodplain 字段已写入）" % xs_points)
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
