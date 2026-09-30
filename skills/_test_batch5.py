# -*- coding: utf-8 -*-
"""第四批 8 个技能的冒烟测试（ArcMap py2.7，exec 独立 namespace 加载）。

测试数据全部造在系统临时目录下，跑完不清理（便于人工查看）。
"""
import os
import sys
import traceback

import numpy as np
import arcpy

SKILLS = r'A:\GisProTest\.arcmapbridge\skills'
TMP = r'C:\wtmp\yghs_b4'  # 纯 ASCII 路径，避免短名/中文导致栅格写入失败
GDB = os.path.join(TMP, 'b4.gdb')
if not os.path.isdir(TMP):
    os.makedirs(TMP)

arcpy.env.overwriteOutput = True

SR = arcpy.SpatialReference(3857)  # Web Mercator，单位米
CELL = 30.0
X0, Y0 = 12000000.0, 3800000.0  # 左下角
ROWS, COLS = 120, 120

PASS, FAIL = [], []
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
    (PASS if ok else FAIL).append(label)
    print('%-4s [%s] rc=%s' % ('PASS' if ok else 'FAIL', label, rc))
    return ok


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


def mk_poly(x, y, w=200.0):
    arr = arcpy.Array([arcpy.Point(x, y), arcpy.Point(x + w, y),
                       arcpy.Point(x + w, y + w), arcpy.Point(x, y + w),
                       arcpy.Point(x, y)])
    return arcpy.Polygon(arr, SR)


def mk_raster(path, arr, nodata=None, int_type=False):
    if int_type:
        arr = arr.astype(np.int32)
    ll = arcpy.Point(X0, Y0)
    ras = arcpy.NumPyArrayToRaster(arr, ll, CELL, CELL,
                                   -9999 if nodata is None else nodata)
    ras.save(path)
    arcpy.DefineProjection_management(path, SR)
    return path


def build_data():
    print('===== 造测试数据 =====')
    if arcpy.Exists(GDB):
        arcpy.Delete_management(GDB)
    arcpy.CreateFileGDB_management(TMP, 'b4.gdb')

    # 地块（面）+ 居民点（点），都带「村」分组字段
    rows = []
    for i in range(6):
        v = u'张村' if i < 3 else u'李村'
        rows.append([mk_poly(X0 + 500 + i * 400, Y0 + 500 + (i % 3) * 400),
                     v, u'耕地' if i % 2 == 0 else u'林地', 4.0 + i])
    mk_fc(GDB + '\\地块', 'POLYGON', [('村', 'TEXT'), ('地类', 'TEXT'), ('面积', 'DOUBLE')], rows)

    prows = []
    for i in range(6):
        v = u'张村' if i < 3 else u'李村'
        prows.append([arcpy.PointGeometry(arcpy.Point(
            X0 + 700 + i * 400, Y0 + 700 + (i % 3) * 400), SR), v, u'居民点%d' % i])
    mk_fc(GDB + '\\居民点', 'POINT', [('村', 'TEXT'), ('名称', 'TEXT')], prows)

    # 起点（用于水文追踪）
    srows = []
    for i in range(3):
        srows.append([arcpy.PointGeometry(arcpy.Point(
            X0 + (10 + i * 30) * CELL, Y0 + (ROWS - 10) * CELL), SR), i])
    mk_fc(GDB + '\\追踪起点', 'POINT', [('序号', 'LONG')], srows)

    # AOI 面（日照分析用）
    mk_fc(GDB + '\\AOI', 'POLYGON', [('名称', 'TEXT')],
          [[mk_poly(X0 + 500, Y0 + 500, 3000.0), u'分析区']])

    # DEM：一个锥形山 + 基底
    yy, xx = np.mgrid[0:ROWS, 0:COLS]
    dem = 100.0 + 0.9 * np.sqrt((yy - 60.0) ** 2 + (xx - 60.0) ** 2)
    mk_raster(os.path.join(TMP, 'dem.tif'), dem.astype(np.float32), -9999.0)

    # 流向栅格：整体向下(row+1)，中间一行向右
    fdr = np.ones((ROWS, COLS), dtype=np.int32) * 4
    fdr[ROWS / 2, :] = 1
    mk_raster(os.path.join(TMP, 'fdr.tif'), fdr, 0, True)

    # 坡度（整型，0~30）与距路（整型）
    slope = (np.sqrt((yy - 90.0) ** 2 + (xx - 30.0) ** 2) * 0.25).astype(np.int32)
    slope = np.clip(slope, 0, 30)
    mk_raster(os.path.join(TMP, 'slope.tif'), slope, -9999, True)
    dist = (np.sqrt((yy - 10.0) ** 2 + (xx - 110.0) ** 2) * 12.0).astype(np.int32)
    dist = np.clip(dist, 0, 9000)
    mk_raster(os.path.join(TMP, 'dist_road.tif'), dist, -9999, True)

    # 标准 schema（字段对照/合并用）
    mk_fc(GDB + '\\标准地块', 'POLYGON',
          [('村名', 'TEXT'), ('地类码', 'TEXT'), ('面积', 'DOUBLE')], [])

    # 另一份异构 shp（字段名故意不一样）
    shp_dir = os.path.join(TMP, 'src_a')
    if not os.path.isdir(shp_dir):
        os.makedirs(shp_dir)
    arcpy.CopyFeatures_management(GDB + '\\地块', os.path.join(shp_dir, '地块A.shp'))
    print('测试数据就绪: %s' % TMP)


def main():
    build_data()
    sa = arcpy.CheckExtension('spatial') == 'Available'
    print('Spatial Analyst 可用: %s' % sa)
    print('===== 开始测试 =====')

    # 1 分组近邻
    run('分组近邻', 'analysis-near-by-group',
        [GDB + '\\地块', u'村', GDB + '\\居民点', u'#'])

    # 2 元数据盘点
    run('元数据盘点', 'data-metadata-dump',
        [TMP, TMP, u'b4_meta', u'#', u'#'])

    # 3 字段对照表
    xref = os.path.join(TMP, 'xref.csv')
    run('字段对照表', 'data-field-cross-ref',
        [TMP, u'Polygon', xref, GDB + '\\标准地块', u'#'])

    # 4 按对照表合并（把 to_field_name 全改成统一值再合并）
    import csv as _csv
    if os.path.isfile(xref):
        out_rows = []
        with open(xref, 'rb') as fh:
            rd = _csv.reader(fh)
            head = [c.decode('utf-8') for c in rd.next()]
            out_rows.append(head)
            for r in rd:
                r = [c.decode('utf-8') for c in r]
                if len(r) > 3 and r[2] == u'村':
                    r[3] = u'村名'
                elif len(r) > 3 and r[2] == u'地类':
                    r[3] = u'地类码'
                out_rows.append(r)
        xref2 = os.path.join(TMP, 'xref_fixed.csv')
        with open(xref2, 'wb') as fh:
            _csv.writer(fh).writerows(
                [[c.encode('utf-8') for c in r] for r in out_rows])
        run('按表合并', 'data-merge-by-crossref',
            [xref2, GDB + '\\合并结果', u'3857', u'村名;地类码;面积'])

    # 5 水文追踪
    run('下游追踪', 'hydro-trace-downstream',
        [GDB + '\\追踪起点', os.path.join(TMP, 'fdr.tif'),
         GDB + '\\追踪线', os.path.join(TMP, 'dem.tif')])

    # 6 最短路径
    run('最短路径', 'path-smooth-shortest',
        [os.path.join(TMP, 'dem.tif'),
         X0 + 10 * CELL, Y0 + (ROWS - 10) * CELL,
         X0 + 110 * CELL, Y0 + 10 * CELL,
         '0.6', GDB + '\\选线结果'])

    if sa:
        # 7 日照
        run('日照山体阴影', 'raster-sun-position-hillshade',
            [GDB + '\\AOI', os.path.join(TMP, 'dem.tif'),
             u'2026-06-21 12:00', '8', os.path.join(TMP, 'hillshade.tif')])

        # 8 适宜性
        crit = os.path.join(TMP, 'criteria.csv')
        with open(crit, 'wb') as fh:
            fh.write(u'\ufeff'.encode('utf-8'))
            w = _csv.writer(fh)
            for r in ([u'坡度', os.path.join(TMP, 'slope.tif'), u'range',
                       u'0 5 5;5 15 3;15 30 1', u'0.6'],
                      [u'距路', os.path.join(TMP, 'dist_road.tif'), u'range',
                       u'0 1200 5;1200 3600 3;3600 9000 1', u'0.4']):
                w.writerow([c.encode('utf-8') for c in r])
        run('加权叠加适宜性', 'suitability-weighted-overlay',
            [crit, os.path.join(TMP, 'suit.tif'),
             os.path.join(TMP, 'slope.tif'), u'>15',
             u'2.0', '9', GDB + '\\候选地块'])
    else:
        print('SKIP 日照山体阴影 / 加权叠加适宜性（无 Spatial Analyst）')

    print('===== 结果: PASS %d / FAIL %d =====' % (len(PASS), len(FAIL)))
    for f in FAIL:
        print('  FAIL: %s' % f)
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
