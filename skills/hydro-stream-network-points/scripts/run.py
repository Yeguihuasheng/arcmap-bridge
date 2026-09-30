# -*- coding: utf-8 -*-
"""
河网转点并计算流域面积与高程 —— ArcMap 版

把编辑好的河网（stream_network）转成线性参考路径，逐折点生成合成测点，给每个点赋上汇流累积值、折算的流域面积（平方英里）与 DEM 高程。用于按汇水面积把河网划分成相对均一的河段。

参数顺序（按地理处理工具原定义）：
  1. 输出要素数据集（成果放这里）
  2. 编辑好的河网要素类（带 ReachName 字段）
  3. 汇流累积栅格（hydro-flowdir-d8 的产物）
  4. 输入 DEM 栅格

用法：
    python run.py <输出要素数据集（成果放这里）> <编辑好的河网要素类（带 ReachName 字段）> <汇流累积栅格（hydro-flowdir-d8 的产物）> <输入 DEM 栅格>
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
        print(u"用法: python run.py <输出要素数据集（成果放这里）> <编辑好的河网要素类（带 ReachName 字段）> <汇流累积栅格（hydro-flowdir-d8 的产物）> <输入 DEM 栅格>")
        return 1
    feature_dataset = argv[0]
    stream_network = argv[1]
    flow_accum = argv[2]
    dem = argv[3]
    if arcpy.CheckExtension(u'spatial') != u'Available':
        raise RuntimeError(u"需要 Spatial Analyst 扩展许可")
    arcpy.CheckOutExtension(u'spatial')
    try:
        arcpy.env.overwriteOutput = True
        if not _has_field(stream_network, u'ReachName'):
            raise ValueError(u"河网里没有 ReachName 字段（路径标识必填）")

        # 路径里程字段：from=线长(km)，to=0（下游端为 0）
        if not _has_field(stream_network, u'from_measure'):
            arcpy.AddField_management(stream_network, u'from_measure', u'DOUBLE')
        arcpy.CalculateField_management(stream_network, u'from_measure',
                                        u'!shape.length@kilometers!',
                                        u'PYTHON_9.3')
        if not _has_field(stream_network, u'to_measure'):
            arcpy.AddField_management(stream_network, u'to_measure', u'DOUBLE')
        arcpy.CalculateField_management(stream_network, u'to_measure', u'0',
                                        u'PYTHON_9.3')

        route = os.path.join(feature_dataset, u'stream_network_route')
        arcpy.CreateRoutes_lr(stream_network, u'ReachName', route,
                              u'TWO_FIELDS', u'from_measure', u'to_measure')
        pts = os.path.join(feature_dataset, u'stream_network_points')
        # 路径转出的点带 M 域，ExtractMultiValuesToPoints 对 M-aware 点
        # 必报 010560（10.8 实测）→ 先禁用 M 域复制一份再采样
        pts_raw = os.path.join(feature_dataset, u'sn_pts_raw')
        arcpy.FeatureVerticesToPoints_management(route, pts_raw)
        # 先在 M-aware 点上把里程落进普通字段（剥 M 后 AGA 取不出 M）
        arcpy.AddGeometryAttributes_management(pts_raw, u'POINT_X_Y_Z_M')
        # 首点 M 值 CreateRoutes 会留 NULL，置 0
        code = (u'def setNull2Zero(m):\n'
                u'    if m is None:\n'
                u'        return 0\n'
                u'    return m')
        arcpy.CalculateField_management(pts_raw, u'POINT_M',
                                        u'setNull2Zero(!POINT_M!)',
                                        u'PYTHON_9.3', code)
        arcpy.DeleteField_management(pts_raw, [u'ORIG_FID', u'POINT_Z'])
        # 再禁用 M 域复制成正式成果（M-aware 会让 Extract 报 010560）
        # 注意必须用 FeatureClassToFeatureClass 重建要素类：
        # CopyFeatures 剥 M 后仍有残留，Extract 照样 010560（实测）
        old_mflag = arcpy.env.outputMFlag
        arcpy.env.outputMFlag = u'Disabled'
        arcpy.FeatureClassToFeatureClass_conversion(
            pts_raw, feature_dataset, u'stream_network_points')
        arcpy.env.outputMFlag = old_mflag
        arcpy.Delete_management(pts_raw)

        # 汇流累积 -> 流域面积（平方英里）
        arcpy.sa.ExtractMultiValuesToPoints(pts, [flow_accum], u'NONE')
        fac_name = arcpy.Describe(flow_accum).baseName
        if not _has_field(pts, u'Watershed_Area_SqMile'):
            arcpy.AddField_management(pts, u'Watershed_Area_SqMile', u'DOUBLE')
        sr = arcpy.Describe(flow_accum).spatialReference
        if sr.linearUnitName == u'Meter':
            cell = float(arcpy.GetRasterProperties_management(
                flow_accum, u'CELLSIZEX').getOutput(0))
            expr = u'((%g * %g) * 0.0000003861) * !%s!' % (cell, cell, fac_name)
            arcpy.CalculateField_management(pts, u'Watershed_Area_SqMile',
                                            expr, u'PYTHON_9.3')
        else:
            print(u"提示: 汇流累积栅格线性单位不是米（%s），面积未换算"
                  % sr.linearUnitName)
        arcpy.DeleteField_management(pts, [fac_name])

        # DEM 高程
        arcpy.sa.ExtractMultiValuesToPoints(pts, [dem], u'NONE')
        dem_name = arcpy.Describe(dem).baseName
        arcpy.AlterField_management(pts, dem_name, u'Z', u'Z')
        arcpy.Delete_management(route)
        cnt = arcpy.GetCount_management(pts).getOutput(0)
        print(u"河网测点 -> %s（%s 个点）" % (pts, cnt))
    finally:
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
