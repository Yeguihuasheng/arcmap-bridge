# -*- coding: utf-8 -*-
"""
生成渔网格网 —— ArcMap 版

按原点、旋转方向、像元宽高（或行列数）、对角点生成规则矩形格网（渔网 Fishnet），单元可选面或线，可选输出格网中心标注点。适用于网格化管理、抽样、分区统计的格网底图；与 `map-create-graticule`（经纬度分幅格网）互补，本技能是平面规则格网。

参数顺序（按地理处理工具原定义）：
  1. 输出格网要素类（面或线）
  2. 原点坐标（x y，空格分隔，坐标系单位）
  3. Y 轴方向点坐标（x y，决定格网旋转角）
  4. 像元宽度（0 或空 = 按行列数自动算）
  5. 像元高度（0 或空 = 按行列数自动算）
  6. 行数（0 或空 = 按像元大小自动算）
  7. 列数（0 或空 = 按像元大小自动算）
  8. 对角点坐标（x y，配合像元大小确定范围）
  9. 是否输出格网中心标注点：LABELS / NO_LABELS
  10. 单元类型：POLYGON（面）/ POLYLINE（线）
  11. 范围模板要素（可选，留空 # 用对角点定范围）
  12. 输出坐标系 WKID（如 4490；0 = 沿用默认）

用法：
    python run.py <输出格网要素类（面或线）> <原点坐标（x y，空格分隔，坐标系单位）> <Y 轴方向点坐标（x y，决定格网旋转角）> <像元宽度（0 或空 = 按行列数自动算）> <像元高度（0 或空 = 按行列数自动算）> <行数（0 或空 = 按像元大小自动算）> <列数（0 或空 = 按像元大小自动算）> <对角点坐标（x y，配合像元大小确定范围）> <是否输出格网中心标注点：LABELS / NO_LABELS> <单元类型：POLYGON（面）/ POLYLINE（线）> <范围模板要素（可选，留空 # 用对角点定范围）> <输出坐标系 WKID（如 4490；0 = 沿用默认）>
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
    if len(argv) < 12:
        print(u"用法: python run.py <输出格网要素类（面或线）> <原点坐标（x y，空格分隔，坐标系单位）> <Y 轴方向点坐标（x y，决定格网旋转角）> <像元宽度（0 或空 = 按行列数自动算）> <像元高度（0 或空 = 按行列数自动算）> <行数（0 或空 = 按像元大小自动算）> <列数（0 或空 = 按像元大小自动算）> <对角点坐标（x y，配合像元大小确定范围）> <是否输出格网中心标注点：LABELS / NO_LABELS> <单元类型：POLYGON（面）/ POLYLINE（线）> <范围模板要素（可选，留空 # 用对角点定范围）> <输出坐标系 WKID（如 4490；0 = 沿用默认）>")
        return 1
    out_fc = argv[0]
    origin = argv[1]
    y_axis = argv[2]
    cell_width = argv[3]
    cell_height = argv[4]
    num_rows = argv[5]
    num_cols = argv[6]
    opposite = argv[7]
    labels = argv[8]
    geometry_type = argv[9]
    template = argv[10]
    out_sr = argv[11]
    def _coord(s):
        s = (s or u'').strip()
        if not s or s == u'#':
            return u'#'
        parts = s.replace(u',', u' ').split()
        if len(parts) < 2:
            raise ValueError(u"坐标格式应为 'x y'：%s" % s)
        return u'%s %s' % (parts[0], parts[1])

    origin = _coord(origin)
    y_axis = _coord(y_axis)
    opposite = _coord(opposite)
    template = template if (template and template.strip() and template.strip() != u'#') else u'#'
    labels = (labels or u'NO_LABELS').strip().upper()
    if labels not in (u'LABELS', u'NO_LABELS'):
        labels = u'NO_LABELS'
    geometry_type = (geometry_type or u'POLYGON').strip().upper()
    if geometry_type not in (u'POLYGON', u'POLYLINE'):
        geometry_type = u'POLYGON'

    try:
        sr = int(float(out_sr))
    except Exception:
        sr = 0
    if sr > 0:
        arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(sr)

    arcpy.env.overwriteOutput = True
    arcpy.CreateFishnet_management(out_fc, origin, y_axis,
                                   cell_width, cell_height,
                                   num_rows, num_cols, opposite,
                                   labels, template, geometry_type)
    cnt = int(arcpy.GetCount_management(out_fc).getOutput(0))
    print(u"格网生成：%s（%d 个单元，类型 %s）" % (out_fc, cnt, geometry_type))
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
