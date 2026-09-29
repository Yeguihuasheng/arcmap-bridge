# -*- coding: utf-8 -*-
"""
要素旋转 —— ArcMap 版

按给定角度旋转整个要素类，支持绕指定坐标点旋转、或绕每个要素自身的质心/真实质心旋转，输出到新的要素类（不改动原始数据）。

参数顺序（按地理处理工具原定义）：
  1. 输入要素类
  2. 输出要素类
  3. 旋转基准（xy / in_feature_centroid / in_feature_true_centroid）
  4. 旋转角度（度，逆时针为正）
  5. 旋转中心 X（xy 模式必填，其它填 0）
  6. 旋转中心 Y（xy 模式必填，其它填 0）

用法：
    python run.py <输入要素类> <输出要素类> <旋转基准（xy / in_feature_centroid / in_feature_true_centroid）> <旋转角度（度，逆时针为正）> <旋转中心 X（xy 模式必填，其它填 0）> <旋转中心 Y（xy 模式必填，其它填 0）>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import math
import arcpy


def rotate_geometry(geom, angle_deg, cx, cy):
    """把几何绕 (cx, cy) 旋转 angle_deg 度（逆时针为正）"""
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    sr = geom.spatialReference
    t = geom.type

    def rp(x, y):
        dx = x - cx
        dy = y - cy
        return arcpy.Point(cx + dx * ca - dy * sa, cy + dx * sa + dy * ca)

    if t == 'point':
        p = geom.firstPoint
        return arcpy.PointGeometry(rp(p.X, p.Y), sr)
    if t == 'multipoint':
        return arcpy.Multipoint(arcpy.Array([rp(p.X, p.Y) for p in geom]), sr)
    if t in ('polyline', 'polygon'):
        parts = []
        for part in geom:
            arr = arcpy.Array([rp(p.X, p.Y) for p in part if p])
            if arr.count:
                parts.append(arr)
        arr_all = arcpy.Array(parts)
        if t == 'polyline':
            return arcpy.Polyline(arr_all, sr)
        return arcpy.Polygon(arr_all, sr)
    raise ValueError(u"不支持旋转的几何类型: %s" % t)


def rotate_center(geom, rotation_value, rotation_x, rotation_y):
    """按 rotation_value 求旋转中心"""
    if rotation_value == 'xy':
        return rotation_x, rotation_y
    if rotation_value == 'in_feature_centroid':
        return geom.centroid.X, geom.centroid.Y
    if rotation_value == 'in_feature_true_centroid':
        return geom.trueCentroid.X, geom.trueCentroid.Y
    raise ValueError(u"未知的 rotation_value: %s" % rotation_value)




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
    if len(argv) < 6:
        print(u"用法: python run.py <输入要素类> <输出要素类> <旋转基准（xy / in_feature_centroid / in_feature_true_centroid）> <旋转角度（度，逆时针为正）> <旋转中心 X（xy 模式必填，其它填 0）> <旋转中心 Y（xy 模式必填，其它填 0）>")
        return 1
    in_features = argv[0]
    out_features = argv[1]
    rotation_value = argv[2]
    rotation_angle = float(argv[3])
    rotation_x = float(argv[4])
    rotation_y = float(argv[5])
    arcpy.env.overwriteOutput = True
    allowed = ('xy', 'in_feature_centroid', 'in_feature_true_centroid')
    if rotation_value not in allowed:
        raise ValueError(u"rotation_value 必须是 %s 之一" % u" / ".join(allowed))

    sr = arcpy.Describe(in_features).spatialReference
    geoms = []
    with arcpy.da.SearchCursor(in_features, ['SHAPE@']) as cursor:
        for row in cursor:
            cx, cy = rotate_center(row[0], rotation_value, rotation_x, rotation_y)
            geoms.append(rotate_geometry(row[0], rotation_angle, cx, cy))

    arcpy.CopyFeatures_management(geoms, out_features)
    print(u"输出要素类: %s（%d 个要素）" % (out_features, len(geoms)))
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
