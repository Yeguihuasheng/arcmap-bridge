# -*- coding: utf-8 -*-
"""
最大内圆 —— ArcMap 版

为面要素类每个图斑求取最大内圆（圆心 + 半径），输出内圆面要素类，可选输出圆心点要素类。常用于判断图斑内部可容纳范围、选址退距分析。

参数顺序（按地理处理工具原定义）：
  1. 输入面要素类
  2. 输出内圆面要素类
  3. 输出圆心点要素类（可空）
  4. 收敛精度（默认 0.01）

用法：
    python run.py <输入面要素类> <输出内圆面要素类> <输出圆心点要素类（可空）> <收敛精度（默认 0.01）>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import arcpy


def converge_to_center(polygon, sr, accuracy, centroids, dists):
    """用收缩逼近求最大内圆圆心与半径"""
    dist = 0.0
    while True:
        try:
            boundary = polygon.boundary()
            point_geom = arcpy.PointGeometry(polygon.centroid, sr)
            min_dist = boundary.distanceTo(point_geom)
            dist += min_dist
            if min_dist <= accuracy or polygon.pointCount == 2:
                centroids.append(point_geom)
                dists.append(dist)
                break
            polygon = polygon.buffer(-min_dist)
        except Exception as e:
            print(u"收敛中断: %s" % e)
            break




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
        print(u"用法: python run.py <输入面要素类> <输出内圆面要素类> <输出圆心点要素类（可空）> <收敛精度（默认 0.01）>")
        return 1
    in_polygons = argv[0]
    out_circle = argv[1]
    out_point = argv[2]
    accuracy = float(argv[3])
    arcpy.env.overwriteOutput = True
    sr = arcpy.Describe(in_polygons).spatialReference
    tmp = arcpy.CreateUniqueName('single', 'in_memory')
    arcpy.MultipartToSinglepart_management(in_polygons, tmp)

    centroids = []
    dists = []
    with arcpy.da.SearchCursor(tmp, ['SHAPE@']) as cursor:
        for row in cursor:
            converge_to_center(row[0], sr, accuracy, centroids, dists)
    arcpy.Delete_management(tmp)

    if not centroids:
        raise ValueError(u"没有求出任何内圆，请检查输入是否为有效面")

    pt_fc = out_point if out_point else r'in_memory\inner_point'
    arcpy.CopyFeatures_management(centroids, pt_fc)
    arcpy.AddField_management(pt_fc, 'radius', 'DOUBLE')
    with arcpy.da.UpdateCursor(pt_fc, ['radius']) as cursor:
        for k, row in enumerate(cursor):
            row[0] = dists[k]
            cursor.updateRow(row)
    arcpy.Buffer_analysis(pt_fc, out_circle, 'radius')
    print(u"输出内圆: %s（%d 个）" % (out_circle, len(centroids)))
    if out_point:
        print(u"输出圆心: %s" % out_point)
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
