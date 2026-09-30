# -*- coding: utf-8 -*-
"""
河流线生成纵剖面测点（带里程与高程） —— ArcMap 版

把河流线转成线性参考路径，按站距加密折点生成纵剖面测点，带 POINT_X/Y/M（里程）与 DEM 高程 Z；可选用校准点（已知里程的控制点）校正路径里程，并算出校准前后里程差。是河道纵剖面图、比降计算的基础数据。

参数顺序（按地理处理工具原定义）：
  1. 输出要素数据集（成果放这里）
  2. 河流线要素类（带 ReachName 字段，按水流方向数字化）
  3. 输入 DEM 栅格
  4. 研究区出口到河口的距离（千米，没有就填 0）
  5. 测点站距（坐标系单位；0=保留原折点）
  6. 校准点要素类（填 # 不校准）
  7. 校准点的路径标识字段（填 # 不校准）
  8. 校准点的里程字段（填 # 不校准）
  9. 校准点搜索半径（如 25 Meters；填 # 用默认）

用法：
    python run.py <输出要素数据集（成果放这里）> <河流线要素类（带 ReachName 字段，按水流方向数字化）> <输入 DEM 栅格> <研究区出口到河口的距离（千米，没有就填 0）> <测点站距（坐标系单位；0=保留原折点）> <校准点要素类（填 # 不校准）> <校准点的路径标识字段（填 # 不校准）> <校准点的里程字段（填 # 不校准）> <校准点搜索半径（如 25 Meters；填 # 用默认）>
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
        print(u"用法: python run.py <输出要素数据集（成果放这里）> <河流线要素类（带 ReachName 字段，按水流方向数字化）> <输入 DEM 栅格> <研究区出口到河口的距离（千米，没有就填 0）> <测点站距（坐标系单位；0=保留原折点）> <校准点要素类（填 # 不校准）> <校准点的路径标识字段（填 # 不校准）> <校准点的里程字段（填 # 不校准）> <校准点搜索半径（如 25 Meters；填 # 用默认）>")
        return 1
    feature_dataset = argv[0]
    flowline = argv[1]
    dem = argv[2]
    km_to_mouth = float(argv[3])
    station_distance = float(argv[4])
    calibration_points = argv[5]
    point_id_field = argv[6]
    measure_field = argv[7]
    search_radius = argv[8]
    if arcpy.CheckExtension(u'3D') != u'Available':
        raise RuntimeError(u"需要 3D Analyst 扩展许可（DEM 采样要用）")
    arcpy.CheckOutExtension(u'3D')
    try:
        arcpy.env.overwriteOutput = True
        if not _has_field(flowline, u'ReachName'):
            raise ValueError(u"河流线里没有 ReachName 字段（路径标识必填）")

        calib = (calibration_points or u'').strip()
        if calib in (u'#', u'None', u'NONE'):
            calib = u''
        srch = (search_radius or u'').strip()
        if srch in (u'#', u''):
            srch = u'25 Meters'

        for f in (u'from_measure', u'to_measure'):
            if not _has_field(flowline, f):
                arcpy.AddField_management(flowline, f, u'DOUBLE')
        arcpy.CalculateField_management(flowline, u'from_measure',
                                        repr(km_to_mouth), u'PYTHON_9.3')
        arcpy.CalculateField_management(
            flowline, u'to_measure',
            u'!shape.length@kilometers! + %s' % repr(km_to_mouth),
            u'PYTHON_9.3')

        # ArcMap 的 LR 工具不支持 in_memory 输出（实测 999999），
        # 中间件一律写输出 GDB 实体，用完删除
        out_gdb = os.path.dirname(feature_dataset)
        if station_distance == 0:
            simp = None
            verts = os.path.join(out_gdb, u'fl_vertices')
            arcpy.CopyFeatures_management(flowline, verts)
        else:
            simp = os.path.join(out_gdb, u'fl_simplify')
            arcpy.SimplifyLine_cartography(flowline, simp, u'POINT_REMOVE',
                                           u'1 Feet')
            verts = os.path.join(out_gdb, u'fl_vertices')
            arcpy.CopyFeatures_management(simp, verts)
            arcpy.Densify_edit(verts, u'DISTANCE', station_distance)

        route = os.path.join(out_gdb, u'fl_route')
        arcpy.CreateRoutes_lr(verts, u'ReachName', route, u'TWO_FIELDS',
                              u'from_measure', u'to_measure')

        pts = os.path.join(feature_dataset, u'flowline_points')
        if not calib:
            arcpy.FeatureVerticesToPoints_management(route, pts)
            # 10.8 的 AddGeometryAttributes 只收组合值 POINT_X_Y_Z_M，
            # 单独 POINT_X/POINT_Y/POINT_M 全部 000800
            arcpy.AddGeometryAttributes_management(pts, u'POINT_X_Y_Z_M')
            arcpy.DeleteField_management(pts, [u'POINT_Z'])
            arcpy.AddField_management(pts, u'POINT_M_uncalibrated', u'DOUBLE')
            arcpy.CalculateField_management(pts, u'POINT_M_uncalibrated',
                                            u'!POINT_M!', u'PYTHON_9.3')
        else:
            if not _has_field(calib, point_id_field):
                raise ValueError(u"校准点里没有标识字段: %s" % point_id_field)
            if not _has_field(calib, measure_field):
                raise ValueError(u"校准点里没有里程字段: %s" % measure_field)
            route_c = os.path.join(out_gdb, u'fl_route_cal')
            arcpy.CalibrateRoutes_lr(route, u'ReachName', calib,
                                     point_id_field, measure_field, route_c,
                                     u'DISTANCE', srch)
            arcpy.FeatureVerticesToPoints_management(route_c, pts)
            arcpy.AddGeometryAttributes_management(pts, u'POINT_X_Y_Z_M')
            arcpy.DeleteField_management(pts, [u'POINT_Z'])
            unc = os.path.join(out_gdb, u'fl_uncal')
            arcpy.LocateFeaturesAlongRoutes_lr(
                pts, route, u'ReachName', station_distance, unc,
                u'ReachName POINT POINT_M_uncalibrated')
            arcpy.JoinField_management(pts, u'OBJECTID', unc, u'OBJECTID',
                                       [u'POINT_M_uncalibrated'])

        arcpy.DeleteField_management(pts, [u'ORIG_FID'])
        arcpy.AddField_management(pts, u'calibration_diff', u'DOUBLE')
        arcpy.CalculateField_management(
            pts, u'calibration_diff',
            u'!POINT_M! - !POINT_M_uncalibrated!', u'PYTHON_9.3')
        arcpy.AddSurfaceInformation_3d(pts, dem, u'Z', 1.0)
        mids = [verts, route]
        if simp:
            mids.append(simp)
        if calib:
            mids += [route_c, unc]
        for t in mids:
            try:
                arcpy.Delete_management(t)
            except Exception:
                pass
        cnt = arcpy.GetCount_management(pts).getOutput(0)
        print(u"纵剖面测点 -> %s（%s 个点%s）"
              % (pts, cnt, u'，已校准' if calib else u''))
    finally:
        arcpy.CheckInExtension(u'3D')
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
