# -*- coding: utf-8 -*-
"""
外业测点插值生成 DEM —— ArcMap 版

把外业实测的高程点（深泓点 + 横断面点）合并后插值成 DEM 栅格，支持 Spline（样条）与 TIN 两种方法，并回算每个测点的「实测高程 - DEM 高程」差值做质量检查。用于缺少现成地形数据、只有实测点时的地形重建。

参数顺序（按地理处理工具原定义）：
  1. 输出要素数据集（须已存在，成果放这里）
  2. 深泓点要素类（带高程字段）
  3. 横断面点要素类（带高程字段）
  4. 高程字段名（默认 Elevation）
  5. 插值方法：Spline（样条）或 TIN
  6. 输出 DEM 像元大小（坐标系单位，如米）
  7. 样条类型：REGULARIZED（规则样条）或 TENSION（张力样条）
  8. 样条权重（REGULARIZED 常用 0.1，TENSION 常用 10）
  9. 参与局部插值的点数（默认 12）

用法：
    python run.py <输出要素数据集（须已存在，成果放这里）> <深泓点要素类（带高程字段）> <横断面点要素类（带高程字段）> <高程字段名（默认 Elevation）> <插值方法：Spline（样条）或 TIN> <输出 DEM 像元大小（坐标系单位，如米）> <样条类型：REGULARIZED（规则样条）或 TENSION（张力样条）> <样条权重（REGULARIZED 常用 0.1，TENSION 常用 10）> <参与局部插值的点数（默认 12）>
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
    if len(argv) < 9:
        print(u"用法: python run.py <输出要素数据集（须已存在，成果放这里）> <深泓点要素类（带高程字段）> <横断面点要素类（带高程字段）> <高程字段名（默认 Elevation）> <插值方法：Spline（样条）或 TIN> <输出 DEM 像元大小（坐标系单位，如米）> <样条类型：REGULARIZED（规则样条）或 TENSION（张力样条）> <样条权重（REGULARIZED 常用 0.1，TENSION 常用 10）> <参与局部插值的点数（默认 12）>")
        return 1
    feature_dataset = argv[0]
    thalweg_points = argv[1]
    field_xs_points = argv[2]
    elev_field = argv[3]
    method = argv[4]
    cell_size = float(argv[5])
    spline_type = argv[6]
    weight = float(argv[7])
    number_points = int(float(argv[8]))
    if arcpy.CheckExtension(u'3D') != u'Available':
        raise RuntimeError(u"需要 3D Analyst 扩展许可（末尾质检采样要用）")
    arcpy.CheckOutExtension(u'3D')
    method_u = (method or u'').strip().upper()
    if method_u == u'SPLINE':
        if arcpy.CheckExtension(u'spatial') != u'Available':
            raise RuntimeError(u"Spline 法需要 Spatial Analyst 扩展许可")
        arcpy.CheckOutExtension(u'spatial')
    try:
        arcpy.env.overwriteOutput = True
        if not arcpy.Exists(feature_dataset):
            raise ValueError(u"要素数据集不存在（请先建一个空的）: %s" % feature_dataset)
        if not _has_field(thalweg_points, elev_field):
            raise ValueError(u"深泓点里没有高程字段: %s" % elev_field)
        if not _has_field(field_xs_points, elev_field):
            raise ValueError(u"横断面点里没有高程字段: %s" % elev_field)
        if cell_size <= 0:
            raise ValueError(u"像元大小必须大于 0")

        out_gdb = os.path.dirname(feature_dataset)
        arcpy.env.workspace = out_gdb
        arcpy.env.compression = u'LZ77'

        # 合并两类实测点
        elevation_points = os.path.join(feature_dataset, u'elevation_points')
        arcpy.Merge_management([thalweg_points, field_xs_points], elevation_points)
        print(u"  合并测点 -> %s" % elevation_points)

        arcpy.env.cellSize = cell_size
        srs = arcpy.Describe(elevation_points).spatialReference
        arcpy.env.outputCoordinateSystem = srs

        # 凸包 + 外扩 1 米做插值范围
        mch = os.path.join(feature_dataset, u'min_convex_hull')
        arcpy.MinimumBoundingGeometry_management(elevation_points, mch,
                                                 u'CONVEX_HULL')
        mch_buf = os.path.join(feature_dataset, u'mch_buffer')
        arcpy.Buffer_analysis(mch, mch_buf, u'1 Meters')

        dem_field = os.path.join(out_gdb, u'DEM_field')
        if method_u == u'SPLINE':
            arcpy.env.extent = mch_buf
            arcpy.env.mask = mch_buf
            dem = arcpy.sa.Spline(elevation_points, elev_field, cell_size,
                                  spline_type, weight, number_points)
            dem.save(dem_field)
            print(u"  Spline 插值 -> %s" % dem_field)
        elif method_u == u'TIN':
            tin_path = os.path.join(out_gdb, u'DEM_field_tin')
            expr = (u"%s %s Mass_Points <None>;%s <None> Hard_Clip <None>"
                    % (elevation_points, elev_field, mch_buf))
            arcpy.CreateTin_3d(tin_path, srs, expr, u'DELAUNAY')
            arcpy.TinRaster_3d(tin_path, dem_field, u'FLOAT', u'LINEAR',
                               u'CELLSIZE', 1, cell_size)
            arcpy.Delete_management(tin_path)
            print(u"  TIN 转栅格 -> %s" % dem_field)
        else:
            raise ValueError(u"method 只能是 Spline 或 TIN: %s" % method)

        arcpy.CalculateStatistics_management(dem_field, 1, 1, [], u'OVERWRITE')

        # 质检：DEM 采样回测点，算 实测 - DEM 差值
        if not _has_field(elevation_points, u'Z'):
            arcpy.AddField_management(elevation_points, u'Z', u'DOUBLE')
        if not _has_field(elevation_points, u'field_dem_diff'):
            arcpy.AddField_management(elevation_points, u'field_dem_diff',
                                      u'DOUBLE')
        arcpy.AddSurfaceInformation_3d(elevation_points, dem_field, u'Z')
        arcpy.CalculateField_management(elevation_points, u'field_dem_diff',
                                        u'!%s! - !Z!' % elev_field,
                                        u'PYTHON_9.3')
        for t in (mch, mch_buf):
            arcpy.Delete_management(t)
        print(u"完成: DEM -> %s；质检差值写在 elevation_points.field_dem_diff"
              % dem_field)
    finally:
        arcpy.CheckInExtension(u'3D')
        arcpy.CheckInExtension(u'spatial')
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
