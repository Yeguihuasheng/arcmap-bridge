# -*- coding: utf-8 -*-
"""
造测试数据：临时 GDB + 三调图层 + 用地图层 + 现状/规划图层 + 分区图层 + 道路线。
供 skills 全面测试使用。
"""
import os
import arcpy

TMP = os.environ.get('TEMP', r'C:\Users\Administrator\AppData\Local\Temp')
GDB = os.path.join(TMP, 'yghs_skill_test.gdb')


def build():
    if arcpy.Exists(GDB):
        arcpy.Delete_management(GDB)
    d = os.path.dirname(GDB)
    if not os.path.isdir(d):
        os.makedirs(d)
    arcpy.CreateFileGDB_management(d, 'yghs_skill_test.gdb')
    sr = arcpy.SpatialReference(4326)  # 简单 WGS84，面积用 shape.area（无投影，但测试够用）

    def _rect(x, y, w=0.05, h=0.05):
        arr = arcpy.Array([arcpy.Point(x, y), arcpy.Point(x + w, y),
                           arcpy.Point(x + w, y + h), arcpy.Point(x, y + h)])
        return arcpy.Polygon(arr)

    # 1. 三调图层（DLBM/DLMC + 面积）
    sd = GDB + r'\三调'
    arcpy.CreateFeatureclass_management(GDB, u'三调', 'POLYGON', spatial_reference=sr)
    arcpy.AddField_management(sd, 'DLBM', 'TEXT', 10)
    arcpy.AddField_management(sd, 'DLMC', 'TEXT', 30)
    arcpy.AddField_management(sd, 'MJ', 'DOUBLE')
    # 三类典型：耕地0101、林地0301、建设用地0601
    data = [
        (u'0101', u'水田', 100.0), (u'0102', u'水浇地', 50.0), (u'0101', u'水田', 30.0),
        (u'0301', u'乔木林地', 80.0), (u'0303', u'红树林地', 20.0),
        (u'0601', u'工业用地', 60.0), (u'0701', u'城镇住宅用地', 40.0),
    ]
    with arcpy.da.InsertCursor(sd, ['SHAPE@', 'DLBM', 'DLMC', 'MJ']) as cur:
        for i, (bm, mc, mj) in enumerate(data):
            x = 120.0 + (i % 3) * 0.1
            y = 30.0 + (i // 3) * 0.1
            cur.insertRow([_rect(x, y), bm, mc, mj])

    # 2. 用地用海图层（编码 + 名称）
    yd = GDB + r'\用地用海'
    arcpy.CreateFeatureclass_management(GDB, u'用地用海', 'POLYGON', spatial_reference=sr)
    arcpy.AddField_management(yd, 'BM', 'TEXT', 10)
    arcpy.AddField_management(yd, 'MC', 'TEXT', 30)
    arcpy.AddField_management(yd, 'MJ', 'DOUBLE')
    yd_data = [(u'0101', u'', 100.0), (u'0102', u'', 50.0), (u'0201', u'', 80.0), (u'0101', u'', 30.0)]
    with arcpy.da.InsertCursor(yd, ['SHAPE@', 'BM', 'MC', 'MJ']) as cur:
        for i, (bm, mc, mj) in enumerate(yd_data):
            cur.insertRow([_rect(120.0 + i * 0.1, 30.0), bm, mc, mj])

    # 3. 现状 / 规划图层（同名 DLBM 字段，用于变化检测）
    xz = GDB + r'\现状'
    gh = GDB + r'\规划'
    for name in (u'现状', u'规划'):
        arcpy.CreateFeatureclass_management(GDB, name, 'POLYGON', spatial_reference=sr)
        arcpy.AddField_management(GDB + '\\' + name, 'DLBM', 'TEXT', 10)
        arcpy.AddField_management(GDB + '\\' + name, 'MJ', 'DOUBLE')
    with arcpy.da.InsertCursor(xz, ['SHAPE@', 'DLBM', 'MJ']) as cur:
        cur.insertRow([_rect(120.0, 30.0), u'0101', 100.0])
        cur.insertRow([_rect(120.1, 30.0), u'0301', 80.0])
    with arcpy.da.InsertCursor(gh, ['SHAPE@', 'DLBM', 'MJ']) as cur:
        cur.insertRow([_rect(120.0, 30.0), u'0101', 100.0])   # 不变
        cur.insertRow([_rect(120.1, 30.0), u'0601', 60.0])    # 变化：0301 -> 0601

    # 4. 分区图层（名称字段）
    zone = GDB + r'\分区'
    arcpy.CreateFeatureclass_management(GDB, u'分区', 'POLYGON', spatial_reference=sr)
    arcpy.AddField_management(zone, 'NAME', 'TEXT', 20)
    with arcpy.da.InsertCursor(zone, ['SHAPE@', 'NAME']) as cur:
        cur.insertRow([_rect(120.0, 30.0), u'A区'])
        cur.insertRow([_rect(120.1, 30.0), u'B区'])

    # 5. 道路线图层（类型字段）
    road = GDB + r'\道路'
    arcpy.CreateFeatureclass_management(GDB, u'道路', 'POLYLINE', spatial_reference=sr)
    arcpy.AddField_management(road, 'TYPE', 'TEXT', 20)
    with arcpy.da.InsertCursor(road, ['SHAPE@', 'TYPE']) as cur:
        import arcpy as ap
        # 两条线
        arr = ap.Array([ap.Point(120.0, 30.0), ap.Point(120.5, 30.5)])
        pl = ap.Polyline(arr)
        cur.insertRow([pl, u'主干路'])
        arr2 = ap.Array([ap.Point(120.1, 30.1), ap.Point(120.6, 30.6)])
        pl2 = ap.Polyline(arr2)
        cur.insertRow([pl2, u'支路'])

    print('GDB =', GDB)
    arcpy.env.workspace = GDB
    for fc in arcpy.ListFeatureClasses():
        print('  %s: %d 条' % (fc.decode('gbk') if isinstance(fc, bytes) else fc,
                              int(arcpy.GetCount_management(GDB + '\\' + fc).getOutput(0))))
    print('BUILD_OK')


if __name__ == '__main__':
    build()
