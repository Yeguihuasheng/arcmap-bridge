# -*- coding: utf-8 -*-
"""
三点定圆 —— ArcMap 版

对点要素类每三个点求一个外接圆（圆心 + 半径），输出圆面要素类，可选输出圆心点要素类。

参数顺序（按地理处理工具原定义）：
  1. 输入点要素类
  2. 输出圆面要素类
  3. 输出圆心点要素类（可空）

用法：
    python run.py <输入点要素类> <输出圆面要素类> <输出圆心点要素类（可空）>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import arcpy


def _det3(m):
    """3x3 行列式（避免依赖 numpy）"""
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))




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
    if len(argv) < 3:
        print(u"用法: python run.py <输入点要素类> <输出圆面要素类> <输出圆心点要素类（可空）>")
        return 1
    in_points = argv[0]
    out_circle = argv[1]
    out_centroid = argv[2]
    arcpy.env.overwriteOutput = True
    desc = arcpy.Describe(in_points)
    if desc.shapeType != 'Point':
        raise ValueError(u"输入必须是点要素类，当前是: %s" % desc.shapeType)
    sr = desc.spatialReference
    pts = [r[0] for r in arcpy.da.SearchCursor(in_points, ['SHAPE@XY'])]
    if len(pts) % 3 != 0:
        raise ValueError(u"点数必须是 3 的倍数，当前 %d 个" % len(pts))

    centroids = []
    radii = []
    for i in range(0, len(pts), 3):
        p1, p2, p3 = pts[i], pts[i + 1], pts[i + 2]
        det_a = _det3([[p1[0], p1[1], 1.0],
                       [p2[0], p2[1], 1.0],
                       [p3[0], p3[1], 1.0]])
        if abs(det_a) < 1e-12:
            print(u"跳过第 %d 组：三点共线，无解" % (i / 3 + 1))
            continue
        b = [[(p[0] * p[0] + p[1] * p[1]) / 2.0, p[1], 1.0] for p in (p1, p2, p3)]
        c = [[p[0], (p[0] * p[0] + p[1] * p[1]) / 2.0, 1.0] for p in (p1, p2, p3)]
        x = _det3(b) / det_a
        y = _det3(c) / det_a
        centroids.append(arcpy.PointGeometry(arcpy.Point(x, y), sr))
        radii.append(((p1[0] - x) ** 2 + (p1[1] - y) ** 2) ** 0.5)

    if not centroids:
        raise ValueError(u"没有任何三点组能定圆（可能全部共线）")

    cen_fc = out_centroid if out_centroid else r'in_memory\circle_centroid'
    arcpy.CopyFeatures_management(centroids, cen_fc)
    arcpy.AddField_management(cen_fc, 'distance', 'DOUBLE')
    with arcpy.da.UpdateCursor(cen_fc, ['distance']) as cursor:
        for k, row in enumerate(cursor):
            row[0] = radii[k]
            cursor.updateRow(row)
    arcpy.Buffer_analysis(cen_fc, out_circle, 'distance')
    print(u"输出圆面: %s（%d 个）" % (out_circle, len(centroids)))
    if out_centroid:
        print(u"输出圆心: %s" % out_centroid)
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
