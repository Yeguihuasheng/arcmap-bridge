# -*- coding: utf-8 -*-
"""第七批 9 个技能的冒烟测试（ArcMap py2.7，exec 独立 namespace 加载）。

测试数据全部造在纯 ASCII 路径 C:\\wtmp\\yghs_b7 下。
重点数值校验：
  * 外业点插值 DEM：质检差值 field_dem_diff 均值近 0
  * 烧切线：烧后像元 = 沿线最低高程
  * 河网转点：流域面积 = 像元数×像元面积×3.861e-7（平方英里）
  * 纵剖面测点：POINT_M 范围 [0, 线长km]，Z 与 DEM 公式一致
  * 洼地识别：只留面积窗口内的坑，POCK_DEP=-50
  * 反射率：与独立复算公式对比（辐射率→日地距离→反射率）
"""
import math
import os
import sys
import traceback

import numpy as np
import arcpy

SKILLS = r'A:\GisProTest\.arcmapbridge\skills'
TMP = r'C:\wtmp\yghs_b7'
GDB = os.path.join(TMP, 'b7.gdb')
FD = os.path.join(GDB, 'FD')
REF = os.path.join(TMP, 'ref')
arcpy.env.overwriteOutput = True

SR = arcpy.SpatialReference(3857)
CELL = 30.0
X0, Y0 = 12300000.0, 3900000.0
ROWS, COLS = 100, 100
FLOOR_Y = Y0 + 1485.0  # 谷底（第 50 行中心）

PASS, FAIL = [], []
CHK_OK, CHK_BAD = [0], [0]
_n = [0]


def run(label, skill, argv):
    script = os.path.join(SKILLS, skill, 'scripts', 'run.py')
    src = open(script, 'rb').read().decode('utf-8')
    lines = src.splitlines()
    if lines and 'coding' in lines[0]:
        lines = lines[1:]
    src = '\n'.join(lines)
    _n[0] += 1
    ns = {'__name__': 'run_%d' % _n[0], '__file__': script}
    try:
        exec(compile(src, script, 'exec'), ns)
        rc = ns['main']([a if not isinstance(a, str) else a.decode('utf-8')
                         for a in argv])
        ok = (rc in (0, None))
    except Exception:
        traceback.print_exc()
        ok = False
        rc = 'EXC'
    finally:
        arcpy.env.extent = None
        arcpy.env.mask = None
        arcpy.env.cellSize = None
        arcpy.env.outputCoordinateSystem = None
        arcpy.env.snapRaster = None
        arcpy.env.workspace = GDB
    (PASS if ok else FAIL).append(label)
    print('%-4s [%s] rc=%s' % ('PASS' if ok else 'FAIL', label, rc))
    return ok


def chk(label, cond, detail=u''):
    if cond:
        CHK_OK[0] += 1
        print(u'  CHK-OK   %s %s' % (label, detail))
    else:
        CHK_BAD[0] += 1
        print(u'  CHK-FAIL %s %s' % (label, detail))


def _u2(v):
    if isinstance(v, unicode):
        return v
    for enc in ('mbcs', 'utf-8', 'gbk'):
        try:
            return v.decode(enc)
        except Exception:
            continue
    return unicode(v)


def mk_fc(path, geom, fields, rows, sr=None):
    d, name = os.path.split(path)
    arcpy.CreateFeatureclass_management(d, name, geom, '', '', '', sr or SR)
    for fn, ft in fields:
        arcpy.AddField_management(path, fn, ft, '', '', 80 if ft == 'TEXT' else None)
    if rows:
        with arcpy.da.InsertCursor(path, ['SHAPE@'] + [f[0] for f in fields]) as ic:
            for r in rows:
                ic.insertRow(r)
    return path


def mk_line(pts):
    arr = arcpy.Array([arcpy.Point(px, py) for px, py in pts])
    return arcpy.Polyline(arr, SR)


def mk_poly(x, y, w, h=None):
    h = h or w
    arr = arcpy.Array([arcpy.Point(x, y), arcpy.Point(x, y + h),
                       arcpy.Point(x + w, y + h), arcpy.Point(x + w, y),
                       arcpy.Point(x, y)])
    return arcpy.Polygon(arr, SR)


def mk_raster(path, arr, nodata=-9999, cell=CELL, ll=None):
    ras = arcpy.NumPyArrayToRaster(arr, ll or arcpy.Point(X0, Y0),
                                   cell, cell, nodata)
    ras.save(path)
    arcpy.DefineProjection_management(path, SR)
    return path


def z_formula(x, y):
    """DEM 高程公式：谷底沿第 50 行，纵坡 0.003，横坡 0.08。"""
    c = int((x - X0) / CELL)
    r = int((Y0 + 3000 - y) / CELL)
    return 100.0 + 0.003 * (c * CELL) + 0.08 * (abs(r - 50) * CELL)


def build_data():
    print('===== 造测试数据 =====')
    if os.path.isdir(TMP):
        import shutil
        shutil.rmtree(TMP)
    os.makedirs(TMP)
    os.makedirs(REF)
    arcpy.CreateFileGDB_management(TMP, 'b7.gdb')
    arcpy.CreateFeatureDataset_management(GDB, 'FD', SR)
    arcpy.env.workspace = GDB

    # 1) DEM：V 形谷（与第六批同公式）
    yy, xx = np.mgrid[0:ROWS, 0:COLS]
    dem = 100.0 + 0.003 * (xx * CELL) + 0.08 * (np.abs(yy - 50.0) * CELL)
    mk_raster(os.path.join(TMP, 'dem.tif'), dem.astype(np.float32))

    # 2) 汇流累积：全 1，谷底行 500
    fac = np.ones((ROWS, COLS), dtype=np.int32)
    fac[50, :] = 500
    mk_raster(os.path.join(TMP, 'fac.tif'), fac, 0)

    # 3) 外业测点：深泓点（谷底线）+ 横断面点（两侧），同带 Elevation
    thal = []
    for i in range(9):
        x = X0 + 300 + i * 300.0
        thal.append([arcpy.PointGeometry(arcpy.Point(x, FLOOR_Y), SR),
                     100.0 + 0.003 * (x - X0)])
    mk_fc(GDB + u'\\深泓点', 'POINT', [(u'Elevation', 'DOUBLE')], thal)
    xs = []
    for cx in (X0 + 600, X0 + 1200, X0 + 1800, X0 + 2400):
        for dy in (-600, -300, 300, 600):
            y = FLOOR_Y + dy
            xs.append([arcpy.PointGeometry(arcpy.Point(cx, y), SR),
                       100.0 + 0.003 * (cx - X0) + 0.08 * abs(dy)])
    mk_fc(GDB + u'\\横断面点', 'POINT', [(u'Elevation', 'DOUBLE')], xs)

    # 4) 河网：R1 两节（右→左，顺水流）+ R2 一支流
    r1a = mk_line([(X0 + 2700, FLOOR_Y), (X0 + 1500, FLOOR_Y)])
    r1b = mk_line([(X0 + 1500, FLOOR_Y), (X0 + 300, FLOOR_Y)])
    r2 = mk_line([(X0 + 2700, FLOOR_Y + 600), (X0 + 1500, FLOOR_Y)])
    mk_fc(GDB + u'\\河网', 'POLYLINE', [(u'ReachName', 'TEXT')],
          [[r1a, u'R1'], [r1b, u'R1'], [r2, u'R2']])

    # 5) 切线：斜穿谷底（x 1200→1800，y 1185→1785）
    mk_fc(GDB + u'\\切线', 'POLYLINE', [(u'名称', 'TEXT')],
          [[mk_line([(X0 + 1200, FLOOR_Y - 300), (X0 + 1800, FLOOR_Y + 300)]),
            u'C1']])

    # 6) 河道面 / 滩地面 / 分类点
    mk_fc(GDB + u'\\河道面', 'POLYGON', [(u'名称', 'TEXT')],
          [[mk_poly(X0 + 300, FLOOR_Y - 300, 2400, 600), u'ch']])
    mk_fc(GDB + u'\\滩地面', 'POLYGON', [(u'名称', 'TEXT')],
          [[mk_poly(X0 + 300, FLOOR_Y - 900, 2400, 1800), u'fp']])
    cls = []
    for cx in (X0 + 1000, X0 + 1500, X0 + 2000):
        cls.append([arcpy.PointGeometry(arcpy.Point(cx, FLOOR_Y), SR), u'河道内'])
        cls.append([arcpy.PointGeometry(arcpy.Point(cx, FLOOR_Y + 500), SR), u'滩地内'])
    cls.append([arcpy.PointGeometry(arcpy.Point(X0 + 1000, FLOOR_Y + 2000), SR), u'外部1'])
    cls.append([arcpy.PointGeometry(arcpy.Point(X0 + 2000, FLOOR_Y + 2000), SR), u'外部2'])
    mk_fc(GDB + u'\\分类点', 'POINT', [(u'名称', 'TEXT')], cls)

    # 7) 出口面（谷底西端小方块）
    mk_fc(GDB + u'\\出口面', 'POLYGON', [(u'名称', 'TEXT')],
          [[mk_poly(X0 + 300, FLOOR_Y - 75, 150), u'S1']])

    # 8) 负值海底 DEM：全 -100，小坑(10x10 格)=-150，大坑(20x20 格)=-180
    bathy = np.full((ROWS, COLS), -100.0, dtype=np.float32)
    bathy[40:50, 40:50] = -150.0   # 300x300m = 90000 m²
    bathy[70:90, 70:90] = -180.0   # 600x600m = 360000 m²
    mk_raster(os.path.join(TMP, 'bathy.tif'), bathy)

    # 9) Landsat 假数据：band1.tif 常量 DN=100 + _MTL.txt
    b1 = np.full((20, 20), 100, dtype=np.int16)
    mk_raster(os.path.join(REF, 'band1.tif'), b1.astype(np.int32), 0)
    mtl = u'''GROUP = L1_METADATA_FILE
  GROUP = PRODUCT_METADATA
    FILE_NAME_BAND_1 = "band1.tif"
    DATE_ACQUIRED = 2020-06-15
  END_GROUP = PRODUCT_METADATA
  GROUP = RADIOMETRIC_RESCALING
    RADIANCE_MAXIMUM_BAND_1 = 200.0
    RADIANCE_MINIMUM_BAND_1 = 10.0
    QUANTIZE_CAL_MAX_BAND_1 = 255
    QUANTIZE_CAL_MIN_BAND_1 = 1
  END_GROUP = RADIOMETRIC_RESCALING
  GROUP = IMAGE_ATTRIBUTES
    SUN_ELEVATION = 60.0
  END_GROUP = IMAGE_ATTRIBUTES
END_GROUP = L1_METADATA_FILE
END
'''
    with open(os.path.join(REF, 'L7_MTL.txt'), 'w') as f:
        f.write(mtl.encode('ascii'))

    print(u'测试数据就绪: %s' % TMP)


def main():
    build_data()
    sa = arcpy.CheckExtension('spatial') == 'Available'
    has3d = arcpy.CheckExtension('3D') == 'Available'
    print('Spatial=%s  3D=%s' % (sa, has3d))
    print('===== 开始测试 =====')
    G = GDB

    if sa and has3d:
        run(u'外业点插值DEM', 'hydro-dem-from-field',
            [FD, G + u'\\深泓点', G + u'\\横断面点', u'Elevation',
             u'Spline', 30.0, u'REGULARIZED', 0.1, 12])
    else:
        print('SKIP 外业点插值DEM（需 Spatial + 3D）')

    if sa:
        run(u'烧切线入DEM', 'hydro-hydrodem',
            [G, G + u'\\切线', os.path.join(TMP, 'dem.tif'), 1])
        run(u'河网转点', 'hydro-stream-network-points',
            [FD, G + u'\\河网', os.path.join(TMP, 'fac.tif'),
             os.path.join(TMP, 'dem.tif')])
        run(u'按出口面划汇水区', 'terrain-delineate-flowpaths',
            [os.path.join(TMP, 'dem.tif'), G + u'\\出口面', G + u'\\汇水区'])
        run(u'洼地识别', 'terrain-identify-geodepressions',
            [os.path.join(TMP, 'bathy.tif'), 0, 200000, G + u'\\洼地面'])
        run(u'Landsat反射率', 'raster-reflectance',
            [REF, os.path.join(REF, 'L7_MTL.txt'), u'ETM+ Thuillier',
             u'true', 1, u'1'])
    else:
        print('SKIP 烧切线/河网转点/汇水区/洼地/反射率（无 Spatial Analyst）')

    run(u'河网整编河流线', 'hydro-flowline', [FD, G + u'\\河网', 3.0])

    if has3d:
        run(u'纵剖面测点', 'hydro-flowline-points',
            [FD, FD + u'\\flowline', os.path.join(TMP, 'dem.tif'),
             0, 100, u'#', u'#', u'#', u'#'])
    else:
        print('SKIP 纵剖面测点（无 3D Analyst）')

    run(u'横断面测点分类', 'hydro-xs-classify-points',
        [G + u'\\分类点', G + u'\\河道面', G + u'\\滩地面', 1.0])

    print('===== 结果: PASS %d / FAIL %d =====' % (len(PASS), len(FAIL)))
    for f in FAIL:
        print(u'  FAIL: %s' % f)

    numeric_checks(sa, has3d)
    print('===== 数值校验: OK %d / BAD %d =====' % (CHK_OK[0], CHK_BAD[0]))


def numeric_checks(sa, has3d):
    print('===== 数值校验 =====')
    G = GDB

    # 1) 外业点插值 DEM：范围合理 + 质检差值近 0
    if sa and has3d:
        try:
            r = arcpy.Raster(G + u'\\DEM_field')
            chk(u'插值DEM-最小值', 95 < float(r.minimum) < 105,
                u'%.1f 期望 ~100' % float(r.minimum))
            chk(u'插值DEM-最大值', 120 < float(r.maximum) < 175,
                u'%.1f 期望 ~155' % float(r.maximum))
            diffs = []
            with arcpy.da.SearchCursor(FD + u'\\elevation_points',
                                       ['field_dem_diff']) as c:
                for (d,) in c:
                    if d is not None:
                        diffs.append(abs(d))
            mean_d = sum(diffs) / len(diffs) if diffs else 999
            chk(u'插值DEM-质检差值', mean_d < 2.5,
                u'|实测-DEM| 均值 %.3f（%d 点）期望 <2.5（Spline 为平滑样条+像元采样）' % (mean_d, len(diffs)))
        except Exception:
            traceback.print_exc()
            chk(u'插值DEM校验', False, u'异常')

        # 2) 烧切线：烧后 = 沿线最低（谷底交点 ~104.5）
        try:
            # 检查点 (X0+1650, Y0+1635) 在切线格 (55,45) 内
            arr_h = arcpy.RasterToNumPyArray(G + u'\\dem_hydro')
            arr_o = arcpy.RasterToNumPyArray(os.path.join(TMP, 'dem.tif'))
            burned = float(arr_h[45, 55])
            orig = float(arr_o[45, 55])
            chk(u'烧线-像元被压低', burned < orig - 5,
                u'%.2f < 原 %.2f' % (burned, orig))
            chk(u'烧线-等于沿线最低', abs(burned - 104.5) < 3.0,
                u'%.2f 期望 ~104.5（谷底交点）' % burned)
            # 远离切线的像元不变
            chk(u'烧线-远处不变', abs(float(arr_h[10, 10]) - float(arr_o[10, 10])) < 0.01,
                u'')
        except Exception:
            traceback.print_exc()
            chk(u'烧线校验', False, u'异常')

        # 3) 河网转点：6 个点（TWO_FIELDS 下每段要素独立成路径：
        #    R1a/R1b 各 2 折点 + R2 2 折点），谷底 5 点流域面积 ~0.174 平方英里
        try:
            pts = []
            with arcpy.da.SearchCursor(FD + u'\\stream_network_points',
                                       ['POINT_X', 'POINT_Y', 'Z',
                                        'Watershed_Area_SqMile']) as c:
                for x, y, z, w in c:
                    pts.append((x, y, z, w))
            chk(u'河网点-6个', len(pts) == 6,
                u'%d 期望 6（TWO_FIELDS 每段独立成路径）' % len(pts))
            fl = [p for p in pts if abs(p[1] - FLOOR_Y) < 1]
            ok_area = all(p[3] is not None and abs(p[3] - 0.174) < 0.02
                          for p in fl)
            chk(u'河网点-谷底面积', ok_area and len(fl) == 5,
                u'谷底 %d 点 ~0.174 平方英里' % len(fl))
            ok_z = all(p[2] is not None and abs(p[2] - z_formula(p[0], p[1])) < 1.0
                       for p in fl)
            chk(u'河网点-谷底高程', ok_z, u'')
        except Exception:
            traceback.print_exc()
            chk(u'河网点校验', False, u'异常')

        # 7) 汇水区：面积 > 500 万 m²（谷底以西 ~810 万）
        try:
            total = 0.0
            n = 0
            with arcpy.da.SearchCursor(G + u'\\汇水区', ['SHAPE@']) as c:
                for (g,) in c:
                    total += g.area
                    n += 1
            chk(u'汇水区-有面', n >= 1, u'%d 个' % n)
            chk(u'汇水区-面积', total > 5000000,
                u'%.0f m²（期望 ~810 万）' % total)
        except Exception:
            traceback.print_exc()
            chk(u'汇水区校验', False, u'异常')

        # 8) 洼地：只留小坑，POCK_DEP=-50
        try:
            rows = []
            with arcpy.da.SearchCursor(G + u'\\洼地面', ['AREA_M', 'POCK_DEP']) as c:
                for a, d in c:
                    rows.append((a, d))
            chk(u'洼地-1个', len(rows) == 1, u'%d 个（大坑 36 万 m² 应被过滤）' % len(rows))
            if rows:
                chk(u'洼地-深度', abs(rows[0][1] + 50) < 0.5,
                    u'POCK_DEP=%.2f 期望 -50' % rows[0][1])
                chk(u'洼地-面积', abs(rows[0][0] - 90000) < 6000,
                    u'%.0f 期望 ~90000' % rows[0][0])
        except Exception:
            traceback.print_exc()
            chk(u'洼地校验', False, u'异常')

        # 9) 反射率：独立复算对比
        try:
            rf = os.path.join(REF, 'ReflectanceB1.tif')
            rd = os.path.join(REF, 'RadianceB1.tif')
            chk(u'反射率-文件齐', os.path.isfile(rf) and os.path.isfile(rd),
                u'keep_rad=true 应两个都在')
            # 独立复算
            gain = (200.0 - 10.0) / (255 - 1)
            rad_exp = gain * (100 - 1) + 10  # 84.0551
            d_csv = os.path.join(SKILLS, 'raster-reflectance', 'resources', 'd.csv')
            with open(d_csv) as f:
                dists = [float(l.strip().split(',')[1]) for l in f.readlines()[2:]
                         if l.strip()]
            d167 = dists[166]  # 2020-06-15 = 儒略日 167
            zenith = math.pi / 6.0
            refl_exp = (math.pi * rad_exp * d167 ** 2) / (1997 * math.cos(zenith))
            arr = arcpy.RasterToNumPyArray(rf, nodata_to_value=-1)
            got = float(arr[arr >= 0].mean())
            chk(u'反射率-数值', abs(got - refl_exp) / refl_exp < 0.01,
                u'%.4f 期望 %.4f（偏差 <1%%）' % (got, refl_exp))
            arr2 = arcpy.RasterToNumPyArray(rd, nodata_to_value=-1)
            got2 = float(arr2[arr2 >= 0].mean())
            chk(u'辐射率-数值', abs(got2 - rad_exp) < 0.5,
                u'%.3f 期望 %.3f' % (got2, rad_exp))
        except Exception:
            traceback.print_exc()
            chk(u'反射率校验', False, u'异常')

    # 4) 河流线整编：2 条河段
    try:
        n = int(arcpy.GetCount_management(FD + u'\\flowline').getOutput(0))
        chk(u'河流线-2条', n == 2, u'%d 期望 2（R1/R2）' % n)
    except Exception:
        traceback.print_exc()
        chk(u'河流线校验', False, u'异常')

    # 5) 纵剖面测点：数量 ~40，M 范围 [0, 2.4]，Z 与公式一致
    if has3d:
        try:
            pts = []
            with arcpy.da.SearchCursor(FD + u'\\flowline_points',
                                       ['POINT_X', 'POINT_Y', 'POINT_M', 'Z']) as c:
                for x, y, m, z in c:
                    pts.append((x, y, m, z))
            chk(u'纵剖面点-数量', 36 <= len(pts) <= 44,
                u'%d 期望 ~40' % len(pts))
            ms = [p[2] for p in pts if p[2] is not None]
            chk(u'纵剖面点-M范围', min(ms) >= -0.01 and 2.3 < max(ms) < 2.5,
                u'[%.3f, %.3f] 期望 max~2.4' % (min(ms), max(ms)))
            fl = [p for p in pts if abs(p[1] - FLOOR_Y) < 1]
            ok_z = all(p[3] is not None and abs(p[3] - z_formula(p[0], p[1])) < 1.0
                       for p in fl)
            chk(u'纵剖面点-谷底Z', ok_z and len(fl) > 20,
                u'谷底 %d 点' % len(fl))
        except Exception:
            traceback.print_exc()
            chk(u'纵剖面点校验', False, u'异常')

    # 6) 测点分类：河道/滩地/外部三档
    try:
        got = {}
        with arcpy.da.SearchCursor(G + u'\\分类点',
                                   [u'名称', u'channel', u'floodplain']) as c:
            for nm, ch, fp in c:
                got.setdefault(_u2(nm), []).append((ch, fp))
        chk(u'分类-河道点', got.get(u'河道内') == [(1, 1)] * 3,
            u'%s' % got.get(u'河道内'))
        chk(u'分类-滩地点', got.get(u'滩地内') == [(0, 1)] * 3,
            u'%s' % got.get(u'滩地内'))
        chk(u'分类-外部点', got.get(u'外部1') == [(0, 0)] and
            got.get(u'外部2') == [(0, 0)], u'')
    except Exception:
        traceback.print_exc()
        chk(u'分类校验', False, u'异常')


if __name__ == '__main__':
    main()
