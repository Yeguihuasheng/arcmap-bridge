# -*- coding: utf-8 -*-
"""第五批 15 个技能的冒烟测试（ArcMap py2.7，exec 独立 namespace 加载）。

测试数据全部造在纯 ASCII 路径 C:\\wtmp\\yghs_b5 下（$TEMP 短名会让栅格保存失败）。
"""
import os
import sys
import traceback

import numpy as np
import arcpy

SKILLS = r'A:\GisProTest\.arcmapbridge\skills'
TMP = r'C:\wtmp\yghs_b5'
GDB = os.path.join(TMP, 'b5.gdb')
RAS = os.path.join(TMP, 'ras')
arcpy.env.overwriteOutput = True

SR = arcpy.SpatialReference(3857)  # Web Mercator，单位米
CELL = 30.0
X0, Y0 = 12300000.0, 3900000.0
ROWS, COLS = 100, 100

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


def mk_fc(path, geom, fields, rows):
    d, name = os.path.split(path)
    arcpy.CreateFeatureclass_management(d, name, geom, '', '', '', SR)
    for fn, ft in fields:
        arcpy.AddField_management(path, fn, ft, '', '', 80 if ft == 'TEXT' else None)
    if rows:
        with arcpy.da.InsertCursor(path, ['SHAPE@'] + [f[0] for f in fields]) as ic:
            for r in rows:
                ic.insertRow(r)
    return path


def mk_poly(x, y, w=400.0, hole=None):
    """外环（逆时针）+ 可选内环（顺时针=真洞）。hole=(hx,hy,hw)"""
    rings = arcpy.Array()
    outer = arcpy.Array([arcpy.Point(x, y), arcpy.Point(x, y + w),
                         arcpy.Point(x + w, y + w), arcpy.Point(x + w, y),
                         arcpy.Point(x, y)])
    rings.add(outer)
    if hole:
        hx, hy, hw = hole
        inner = arcpy.Array([arcpy.Point(hx, hy), arcpy.Point(hx, hy + hw),
                             arcpy.Point(hx + hw, hy + hw), arcpy.Point(hx + hw, hy),
                             arcpy.Point(hx, hy)])
        rings.add(inner)
    return arcpy.Polygon(rings, SR)


def mk_line(pts):
    arr = arcpy.Array([arcpy.Point(px, py) for px, py in pts])
    return arcpy.Polyline(arr, SR)


def mk_raster(path, arr, nodata=-9999):
    ll = arcpy.Point(X0, Y0)
    ras = arcpy.NumPyArrayToRaster(arr, ll, CELL, CELL, nodata)
    ras.save(path)
    arcpy.DefineProjection_management(path, SR)
    return path


def build_data():
    print('===== 造测试数据 =====')
    if os.path.isdir(TMP):
        import shutil
        shutil.rmtree(TMP)
    os.makedirs(TMP)
    os.makedirs(RAS)
    arcpy.CreateFileGDB_management(TMP, 'b5.gdb')

    # 8 个点：2 组各 4 个（乙组整体 Y 抬 2000 避免与甲组重合）
    prows = []
    for i in range(8):
        g = u'甲组' if i < 4 else u'乙组'
        x = X0 + 500 + (i % 4) * 300 + (137 if i % 4 in (1,) else 0)
        y = Y0 + 500 + (i % 4) * 250 + (91 if i % 4 in (2,) else 0)
        if i >= 4:
            y += 2000
        prows.append([arcpy.PointGeometry(arcpy.Point(x, y), SR), g, i % 4 + 1, u'点%d' % i])
    mk_fc(GDB + '\\点位', 'POINT',
          [('组', 'TEXT'), ('序号', 'LONG'), ('名称', 'TEXT')], prows)

    # 参照点 2 个（蜘蛛图）
    rrows = [arcpy.PointGeometry(arcpy.Point(X0 + 300, Y0 + 300), SR),
             arcpy.PointGeometry(arcpy.Point(X0 + 1500, Y0 + 1200), SR)]
    mk_fc(GDB + '\\设施点', 'POINT', [], [[g] for g in rrows])

    # 甜甜圈面（填洞）+ 普通面
    donut = mk_poly(X0 + 300, Y0 + 300, 600, hole=(X0 + 450, Y0 + 450, 150))
    plain = mk_poly(X0 + 1200, Y0 + 300, 500)
    mk_fc(GDB + '\\带洞面', 'POLYGON', [('名称', 'TEXT')],
          [[donut, u'甜甜圈'], [plain, u'实心']])

    # 线（打断用）：水平直线 3000m
    line = mk_line([(X0 + 200, Y0 + 2000), (X0 + 3200, Y0 + 2000)])
    mk_fc(GDB + '\\道路', 'POLYLINE', [('路名', 'TEXT')], [[line, u'一号路']])

    # 断点：线上 1/3 与 2/3 处（严格在线上）
    m1 = line.positionAlongLine(1000.0, False)
    m2 = line.positionAlongLine(2000.0, False)
    mk_fc(GDB + '\\断点', 'POINT', [], [[m1], [m2]])

    # 重叠面：输入方块压住参照方块的一半
    inp = mk_poly(X0 + 300, Y0 + 2600, 600)
    ref = mk_poly(X0 + 600, Y0 + 2600, 600)
    mk_fc(GDB + '\\被挖面', 'POLYGON', [('名称', 'TEXT')], [[inp, u'A']])
    mk_fc(GDB + '\\掩膜面', 'POLYGON', [('名称', 'TEXT')], [[ref, u'B']])

    # 按分：参照面 2 块各带 POP=100，输入面同时压住两块各一半
    r1 = mk_poly(X0 + 2000, Y0 + 300, 500)
    r2 = mk_poly(X0 + 2500, Y0 + 300, 500)
    mk_fc(GDB + '\\统计面', 'POLYGON', [('POP', 'DOUBLE')],
          [[r1, 100.0], [r2, 100.0]])
    grid = mk_poly(X0 + 2250, Y0 + 300, 500)
    mk_fc(GDB + '\\网格', 'POLYGON', [('网格号', 'TEXT')], [[grid, u'G1']])

    # DEM：锥形山
    yy, xx = np.mgrid[0:ROWS, 0:COLS]
    dem = 100.0 + 0.8 * np.sqrt((yy - 50.0) ** 2 + (xx - 50.0) ** 2)
    mk_raster(os.path.join(TMP, 'dem.tif'), dem.astype(np.float32))

    # 流向（全向下 4）+ 汇流累积（现场算）
    fdr = np.ones((ROWS, COLS), dtype=np.int32) * 4
    mk_raster(os.path.join(RAS, 'fdr.tif'), fdr, 0)

    # 出水口点：某列中部
    outp = arcpy.PointGeometry(arcpy.Point(
        X0 + 50 * CELL, Y0 + 30 * CELL), SR)
    mk_fc(GDB + '\\出水口', 'POINT', [('编号', 'LONG')], [[outp, 1]])

    # 8bit 地类栅格（NoData 测试用，含 255）
    lc = np.full((60, 60), 11, dtype=np.uint8)
    lc[:10, :] = 255
    lc[30:, 30:] = 21
    mk_raster(os.path.join(RAS, 'lc_8bit.tif'), lc.astype(np.int32), 0)

    print('测试数据就绪: %s' % TMP)


def main():
    build_data()
    sa = arcpy.CheckExtension('spatial') == 'Available'
    has3d = arcpy.CheckExtension('3D') == 'Available'
    print('Spatial=%s  3D=%s' % (sa, has3d))
    print('===== 开始测试 =====')

    G = GDB
    run('凸包', 'geom-convex-hull', [G + '\\点位', G + '\\凸包', u'组', u'#'])
    run('凸包+缓冲', 'geom-convex-hull', [G + '\\点位', G + '\\凸包buf', u'#', u'50 Meters'])

    run('点连面', 'geom-points-to-polygon',
        [G + '\\点位', G + '\\连面', u'组', u'序号'])

    run('填洞', 'geom-fill-holes', [G + '\\带洞面', G + '\\填洞面'])

    run('泰森', 'geom-thiessen-polygons', [G + '\\点位', G + '\\泰森面'])

    run('蜘蛛图', 'geom-spider-graph',
        [G + '\\点位', G + '\\设施点', G + '\\蜘蛛线'])

    run('点打断线', 'geom-split-line-at-point',
        [G + '\\道路', G + '\\断点', G + '\\打断线', u'#'])

    run('折点转点', 'geom-extract-points', [G + '\\道路', G + '\\折点', u'ALL'])
    run('面取真质心', 'geom-extract-points', [G + '\\带洞面', G + '\\真质心', u'TRUE_CENTROID'])

    run('内向缓冲', 'geom-inside-buffer',
        [G + '\\带洞面', 50.0, G + '\\内核面'])

    run('挖除重叠', 'geom-delete-overlap',
        [G + '\\被挖面', G + '\\掩膜面', G + '\\剩余面'])

    run('面积按分', 'geom-split-area-by-ratio',
        [G + '\\网格', G + '\\统计面', u'POP', G + '\\按分面'])

    if sa:
        run('D8流向汇流', 'hydro-flowdir-d8',
            [os.path.join(TMP, 'dem.tif'), TMP])
        run('逐点流域', 'hydro-watershed-by-point',
            [G + '\\出水口', u'编号', os.path.join(RAS, 'fdr.tif'),
             os.path.join(RAS, 'fdr.tif'), u'90',
             os.path.join(RAS, 'lc_8bit.tif'), G + '\\流域面'])
    else:
        print('SKIP D8流向汇流 / 逐点流域（无 Spatial Analyst）')

    if has3d:
        run('地形剖面', 'terrain-profile',
            [os.path.join(TMP, 'dem.tif'), G + '\\道路', G + '\\剖面表', u'#'])
    else:
        print('SKIP 地形剖面（无 3D Analyst）')

    run('栅格定义坐标系', 'raster-define-projection', [RAS, u'3857'])
    run('栅格定义NoData', 'raster-define-nodata', [RAS, u'1 255'])

    print('===== 结果: PASS %d / FAIL %d =====' % (len(PASS), len(FAIL)))
    for f in FAIL:
        print('  FAIL: %s' % f)

    # ---- 数值校验 ----
    print('===== 数值校验 =====')
    try:
        with arcpy.da.SearchCursor(GDB + '\\带洞面', ['SHAPE@', u'名称']) as c:
            for g, nm in c:
                print(u'  原始[%s] 面积=%.0f 部件=%d' % (nm, g.area, g.partCount))
        with arcpy.da.SearchCursor(GDB + '\\填洞面', ['SHAPE@', u'名称']) as c:
            for g, nm in c:
                print(u'  填后[%s] 面积=%.0f 部件=%d' % (nm, g.area, g.partCount))
        with arcpy.da.SearchCursor(GDB + '\\按分面', ['POP']) as c:
            for (v,) in c:
                print(u'  按分 POP=%.2f（期望 100.00：网格各压两块参照面一半，50+50）' % v)
        with arcpy.da.SearchCursor(GDB + '\\内核面', ['SHAPE@', u'名称']) as c:
            for g, nm in c:
                print(u'  内侧环带[%s] 面积=%.0f（实心期望 90000=500²-400²）' % (nm, g.area))
        with arcpy.da.SearchCursor(GDB + '\\剩余面', ['SHAPE@']) as c:
            for (g,) in c:
                print(u'  挖后面积=%.0f（期望 180000：360000-重叠180000）' % g.area)
        with arcpy.da.SearchCursor(GDB + '\\流域面', ['WS_ID']) as c:
            ids = [r[0] for r in c]
            print(u'  流域 WS_ID=%s' % ids)
    except Exception:
        traceback.print_exc()
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
