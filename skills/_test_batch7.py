# -*- coding: utf-8 -*-
"""第六批 15 个技能的冒烟测试（ArcMap py2.7，exec 独立 namespace 加载）。

测试数据全部造在纯 ASCII 路径 C:\\wtmp\\yghs_b6 下。
重点数值校验：
  * 多环缓冲负距离 = 真内缩（800x800=640000）
  * GPX wpt/trk 数量与经纬度范围（3857 自动投影 4326）
  * BLOB 写入->导出字节回环一致
  * 切割线把 1000x1000 面切成两个 500x1000
  * 经纬网 6 条线（112/112.5/113 x 30/30.5/31）
  * 去趋势后谷底值 ~0
  * 水面带宽度 ~270m（阈值 10m / 坡度 0.08）
"""
import os
import sys
import traceback
import xml.etree.ElementTree as ET

import numpy as np
import arcpy

SKILLS = r'A:\GisProTest\.arcmapbridge\skills'
TMP = r'C:\wtmp\yghs_b6'
GDB = os.path.join(TMP, 'b6.gdb')
arcpy.env.overwriteOutput = True

SR = arcpy.SpatialReference(3857)  # Web Mercator，单位米
CELL = 30.0
X0, Y0 = 12300000.0, 3900000.0
ROWS, COLS = 100, 100  # DEM 覆盖 3000x3000 米
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
        # 某些技能改了 env.mask/extent/cellSize，跑完必须复位，否则污染后续测试
        arcpy.env.extent = None
        arcpy.env.mask = None
        arcpy.env.cellSize = None
        arcpy.env.outputCoordinateSystem = None
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


def mk_line(pts):
    arr = arcpy.Array([arcpy.Point(px, py) for px, py in pts])
    return arcpy.Polyline(arr, SR)


def mk_poly(x, y, w, h=None):
    h = h or w
    arr = arcpy.Array([arcpy.Point(x, y), arcpy.Point(x, y + h),
                       arcpy.Point(x + w, y + h), arcpy.Point(x + w, y),
                       arcpy.Point(x, y)])
    return arcpy.Polygon(arr, SR)


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
    arcpy.CreateFileGDB_management(TMP, 'b6.gdb')
    arcpy.env.workspace = GDB

    # 1) 点位 3 个（GPX wpt）：名称 + 备注
    prows = [[arcpy.PointGeometry(arcpy.Point(X0 + 500 + i * 300, Y0 + 600), SR),
              u'观景点%d' % (i + 1), u'高程采样点'] for i in range(3)]
    mk_fc(GDB + u'\\点位', 'POINT', [(u'名称', 'TEXT'), (u'备注', 'TEXT')], prows)

    # 2) 河流线（GPX trk + 去趋势谷底线）：沿谷底每 100m 一个折点
    fpts = [(X0 + 300 + i * 100.0, FLOOR_Y) for i in range(25)]  # 300..2700
    mk_fc(GDB + u'\\河流线', 'POLYLINE', [(u'名称', 'TEXT')],
          [[mk_line(fpts), u'测试河']])

    # 3) 地块 1000x1000（多环缓冲正/负 + 切割对象）
    mk_fc(GDB + u'\\地块', 'POLYGON', [(u'编号', 'TEXT')],
          [[mk_poly(X0 + 4000, Y0 + 500, 1000), u'G1']])

    # 4) 切割线：垂直横贯地块（x=4500，两端超出）
    mk_fc(GDB + u'\\切割线', 'POLYLINE', [(u'名称', 'TEXT')],
          [[mk_line([(X0 + 4500, Y0 + 100), (X0 + 4500, Y0 + 2000)]), u'C1']])

    # 5) 路网：水平线 + 垂直线，交于 (4500, 2500)
    mk_fc(GDB + u'\\路网', 'POLYLINE', [(u'路名', 'TEXT')],
          [[mk_line([(X0 + 4000, Y0 + 2500), (X0 + 5000, Y0 + 2500)]), u'一横'],
           [mk_line([(X0 + 4500, Y0 + 2000), (X0 + 4500, Y0 + 3000)]), u'一纵']])

    # 6) 河道面 2400x600，谷底居中
    mk_fc(GDB + u'\\河道面', 'POLYGON', [(u'名称', 'TEXT')],
          [[mk_poly(X0 + 300, Y0 + 1200, 2400, 600), u'河段1']])

    # 7) 横断面 3 条（垂直跨河道），长 800，编号 S1/S2/S3
    xsrows = []
    for i, cx in enumerate((X0 + 1000, X0 + 1500, X0 + 2000)):
        xsrows.append([mk_line([(cx, Y0 + 1100), (cx, Y0 + 1900)]), u'S%d' % (i + 1)])
    mk_fc(GDB + u'\\横断面', 'POLYLINE', [(u'SEQ', 'TEXT')], xsrows)

    # 8) 镇区 4 块（融合拼接用）
    towns = [(X0 + 5500, Y0 + 500, u'甲镇', u'东风'), (X0 + 5500, Y0 + 900, u'甲镇', u'南湖'),
             (X0 + 6000, Y0 + 500, u'乙镇', u'西河'), (X0 + 6000, Y0 + 900, u'乙镇', u'北岭')]
    mk_fc(GDB + u'\\镇区', 'POLYGON', [(u'镇', 'TEXT'), (u'村名', 'TEXT')],
          [[mk_poly(x, y, 300), z, c] for (x, y, z, c) in towns])

    # 9) BLOB 表 + 源文件目录
    arcpy.CreateTable_management(GDB, u'照片表')
    arcpy.AddField_management(GDB + u'\\照片表', u'名称', 'TEXT', '', '', 50)
    arcpy.AddField_management(GDB + u'\\照片表', u'数据', 'BLOB')
    with arcpy.da.InsertCursor(GDB + u'\\照片表', [u'名称']) as ic:
        for nm in (u'A', u'B', u'C'):
            ic.insertRow([nm])
    blob_dir = os.path.join(TMP, 'blobs')
    os.makedirs(blob_dir)
    for nm, n in ((u'A', 100), (u'B', 200), (u'C', 300)):
        with open(os.path.join(blob_dir, nm + '.jpg'), 'wb') as f:
            f.write(('BLOBTEST_' + nm) * n)

    # 10) DEM：V 形谷，谷底沿第 50 行，纵坡 0.003，横坡 0.08
    yy, xx = np.mgrid[0:ROWS, 0:COLS]
    dem = 100.0 + 0.003 * (xx * CELL) + 0.08 * (np.abs(yy - 50.0) * CELL)
    mk_raster(os.path.join(TMP, 'dem.tif'), dem.astype(np.float32))

    print(u'测试数据就绪: %s' % TMP)


def main():
    build_data()
    sa = arcpy.CheckExtension('spatial') == 'Available'
    print('Spatial=%s' % sa)
    print('===== 开始测试 =====')

    G = GDB

    # ---- 工具类 ----
    run(u'多环缓冲-正', 'tool-multi-ring-buffers',
        [G + u'\\地块', u'100;300', G + u'\\多环面', u'NONE'])
    run(u'多环缓冲-负内缩', 'tool-multi-ring-buffers',
        [G + u'\\地块', u'-100', G + u'\\内缩面', u'NONE'])

    run(u'GPX-点', 'tool-features-to-gpx',
        [G + u'\\点位', u'名称', u'备注', os.path.join(TMP, 'pts.gpx')])
    run(u'GPX-线', 'tool-features-to-gpx',
        [G + u'\\河流线', u'名称', u'#', os.path.join(TMP, 'track.gpx')])

    run(u'文件写BLOB', 'tool-file-to-blob',
        [G + u'\\照片表', u'数据', u'名称', os.path.join(TMP, 'blobs'), u'.jpg'])
    run(u'BLOB导文件', 'tool-blob-to-file',
        [G + u'\\照片表', u'数据', u'名称', os.path.join(TMP, 'blob_out'), u'.jpg'])

    run(u'数据集范围', 'tool-dataset-extent-to-features',
        [G, G + u'\\范围面'])
    run(u'融合拼接', 'tool-dissolve-fields',
        [G + u'\\镇区', u'镇', u'村名', G + u'\\镇区融合', u';'])

    run(u'经纬网', 'map-create-graticule',
        [u'112 30 113 31', 0.5, G + u'\\格网线'])
    run(u'元数据XML', 'meta-export-xml',
        [G + u'\\点位;' + G + u'\\河流线', os.path.join(TMP, 'xml')])

    # ---- 几何类 ----
    run(u'切割线切面', 'geom-cut-by-line',
        [G + u'\\地块', G + u'\\切割线', G + u'\\切分面'])
    run(u'线交点', 'geom-line-junction-to-point',
        [G + u'\\路网', G + u'\\节点', u'YES'])

    # ---- 水文类（需 Spatial Analyst）----
    if sa:
        run(u'河道中心线', 'hydro-centerline',
            [G + u'\\河道面', 5.0, 3.0, G + u'\\中心线'])
        run(u'河道坡度', 'hydro-channel-slope',
            [os.path.join(TMP, 'dem.tif'), G + u'\\河道面', 1.0,
             os.path.join(TMP, 'ch_slope.tif')])
        run(u'横断面测点', 'hydro-xs-points',
            [G + u'\\横断面', u'SEQ', 100.0, os.path.join(TMP, 'dem.tif'),
             G + u'\\测点'])
        run(u'DEM去趋势', 'hydro-detrend-dem',
            [os.path.join(TMP, 'dem.tif'), G + u'\\河流线', 15,
             os.path.join(TMP, 'detrend.tif')])
        run(u'水面范围', 'hydro-water-surface-extent',
            [os.path.join(TMP, 'detrend.tif'), 10.0, 30.0, G + u'\\水面面'])
    else:
        print('SKIP 水文 5 项（无 Spatial Analyst）')

    print('===== 结果: PASS %d / FAIL %d =====' % (len(PASS), len(FAIL)))
    for f in FAIL:
        print(u'  FAIL: %s' % f)

    numeric_checks(sa)
    print('===== 数值校验: OK %d / BAD %d =====' % (CHK_OK[0], CHK_BAD[0]))


def numeric_checks(sa):
    print('===== 数值校验 =====')
    G = GDB

    # 1) 多环缓冲：ROUND 端点是圆角，面积 = 1000²+4000d+πd²；
    #    负 -100 → 800²=640000
    import math
    try:
        d = {}
        with arcpy.da.SearchCursor(G + u'\\多环面', ['DIST', 'SHAPE@']) as c:
            for dist, g in c:
                d[round(dist)] = g.area
        exp100 = 1000000 + 4000 * 100 + math.pi * 100 ** 2  # 1431416
        exp300 = 1000000 + 4000 * 300 + math.pi * 300 ** 2  # 2482743
        chk(u'多环-环数', len(d) == 2, u'DIST=%s' % sorted(d))
        chk(u'多环-100面积', abs(d.get(100, 0) - exp100) < 3000,
            u'%.0f 期望 %.0f（圆角公式）' % (d.get(100, -1), exp100))
        chk(u'多环-300面积', abs(d.get(300, 0) - exp300) < 3000,
            u'%.0f 期望 %.0f（圆角公式）' % (d.get(300, -1), exp300))
        with arcpy.da.SearchCursor(G + u'\\内缩面', ['DIST', 'SHAPE@']) as c:
            rows = [(round(dist), g.area) for dist, g in c]
        chk(u'负内缩-DIST为负', len(rows) == 1 and rows[0][0] == -100, u'%s' % rows)
        chk(u'负内缩-面积640000', len(rows) == 1 and abs(rows[0][1] - 640000) < 2000,
            u'%s 期望 640000' % (rows[0][1] if rows else -1))
    except Exception:
        traceback.print_exc()
        chk(u'多环校验', False, u'异常')

    # 2) GPX：3 wpt + 1 trk，经纬度范围合理（3857→4326）
    try:
        t = ET.parse(os.path.join(TMP, 'pts.gpx'))
        ns = '{http://www.topografix.com/GPX/1/1}'
        wpts = t.getroot().findall(ns + 'wpt')
        chk(u'GPX-wpt数', len(wpts) == 3, u'%d' % len(wpts))
        ok_geo = all(-180 < float(w.get('lon')) < 180 and -90 < float(w.get('lat')) < 90
                     for w in wpts)
        lon0 = float(wpts[0].get('lon')) if wpts else 0
        lat0 = float(wpts[0].get('lat')) if wpts else 0
        chk(u'GPX-wpt经纬度', ok_geo and 110 < lon0 < 111 and 32 < lat0 < 34,
            u'lon=%.4f lat=%.4f（期望 ~110.35/32.97）' % (lon0, lat0))
        chk(u'GPX-wpt名称', all(w.find(ns + 'name') is not None and
                                w.find(ns + 'name').text for w in wpts), u'')
        t2 = ET.parse(os.path.join(TMP, 'track.gpx'))
        trks = t2.getroot().findall(ns + 'trk')
        chk(u'GPX-trk数', len(trks) == 1, u'%d' % len(trks))
        seg = trks[0].findall(ns + 'trkseg') if trks else []
        chk(u'GPX-trkseg有测点', len(seg) == 1 and len(seg[0]) == 25,
            u'%d 段 %d 点（期望 1 段 25 点）' % (len(seg), len(seg[0]) if seg else 0))
    except Exception:
        traceback.print_exc()
        chk(u'GPX校验', False, u'异常')

    # 3) BLOB 回环：字节一致（'BLOBTEST_X' 10 字符 → A=1000/B=2000/C=3000）
    try:
        src = {}
        for nm, n in ((u'A', 100), (u'B', 200), (u'C', 300)):
            with open(os.path.join(TMP, 'blobs', nm + '.jpg'), 'rb') as f:
                src[nm] = f.read()
        ok = True
        for nm in (u'A', u'B', u'C'):
            with open(os.path.join(TMP, 'blob_out', nm + '.jpg'), 'rb') as f:
                if f.read() != src[nm]:
                    ok = False
        chk(u'BLOB回环字节一致', ok, u'A/B/C 三文件')
        with arcpy.da.SearchCursor(G + u'\\照片表', [u'名称', u'数据']) as c:
            sizes = {_u2(nm): len(_blob(b)) for nm, b in c}
        chk(u'BLOB库内长度', sizes == {u'A': 1000, u'B': 2000, u'C': 3000},
            u'%s' % sizes)
    except Exception:
        traceback.print_exc()
        chk(u'BLOB校验', False, u'异常')

    # 4) 数据集范围：覆盖全部要素类，含已知 FCOUNT
    try:
        names = []
        with arcpy.da.SearchCursor(G + u'\\范围面', ['DS_NAME', 'FCOUNT']) as c:
            for nm, fc in c:
                names.append((_u2(nm), fc))
        need = (u'点位', u'河流线', u'地块', u'切割线', u'路网', u'河道面', u'横断面', u'镇区')
        chk(u'范围-覆盖已知FC', all(nm in dict(names) for nm in need),
            u'共 %d 个数据集' % len(names))
        chk(u'范围-点位FCOUNT=3', dict(names).get(u'点位') == 3, u'%s' % dict(names).get(u'点位'))
    except Exception:
        traceback.print_exc()
        chk(u'范围校验', False, u'异常')

    # 5) 融合拼接：甲镇 CAT_村名=东风;南湖
    try:
        got = {}
        with arcpy.da.SearchCursor(G + u'\\镇区融合', [u'镇', u'CAT_村名']) as c:
            for z, v in c:
                got[_u2(z)] = _u2(v)
        chk(u'融合-两组', set(got) == {u'甲镇', u'乙镇'}, u'%s' % got)
        chk(u'融合-甲镇清单', got.get(u'甲镇') == u'东风;南湖', u'%s' % got.get(u'甲镇'))
        chk(u'融合-乙镇清单', got.get(u'乙镇') == u'西河;北岭', u'%s' % got.get(u'乙镇'))
    except Exception:
        traceback.print_exc()
        chk(u'融合校验', False, u'异常')

    # 6) 经纬网：6 条（3 经 + 3 纬），DEG 值正确
    try:
        lines = []
        with arcpy.da.SearchCursor(G + u'\\格网线', ['LINE', 'DEG', 'DMS']) as c:
            for ln, deg, dms in c:
                lines.append((_u2(ln), round(deg, 4), _u2(dms)))
        ns = sorted(d for t, d, m in lines if t == u'N-S')
        ew = sorted(d for t, d, m in lines if t == u'E-W')
        chk(u'格网-总条数', len(lines) == 6, u'%d 期望 6' % len(lines))
        chk(u'格网-经线值', ns == [112.0, 112.5, 113.0], u'%s' % ns)
        chk(u'格网-纬线值', ew == [30.0, 30.5, 31.0], u'%s' % ew)
        chk(u'格网-DMS标注', any(u'112°30' in m for t, d, m in lines), u'')
    except Exception:
        traceback.print_exc()
        chk(u'格网校验', False, u'异常')

    # 7) 元数据 XML：2 个文件非空且含 metadata
    try:
        files = [f for f in os.listdir(os.path.join(TMP, 'xml')) if f.endswith('.xml')]
        chk(u'元数据-2个XML', len(files) == 2, u'%s' % files)
        ok = True
        for f in files:
            p = os.path.join(TMP, 'xml', f)
            sz = os.path.getsize(p)
            if sz < 200:
                ok = False
            with open(p, 'rb') as fh:
                head = fh.read(2000)
            if b'Metadata' not in head and b'metadata' not in head:
                ok = False
        chk(u'元数据-内容非空', ok, u'')
    except Exception:
        traceback.print_exc()
        chk(u'元数据校验', False, u'异常')

    # 8) 切割：2 块各 500000
    try:
        areas = []
        with arcpy.da.SearchCursor(G + u'\\切分面', ['SHAPE@']) as c:
            for (g,) in c:
                areas.append(g.area)
        chk(u'切割-2块', len(areas) == 2, u'%d 块' % len(areas))
        chk(u'切割-面积各500000', len(areas) == 2 and
            all(abs(a - 500000) < 1000 for a in areas), u'%s' % [round(a) for a in areas])
    except Exception:
        traceback.print_exc()
        chk(u'切割校验', False, u'异常')

    # 9) 线交点：1 个，位于 (4500, 2500)
    try:
        pts = []
        with arcpy.da.SearchCursor(G + u'\\节点', ['X', 'Y', 'CNT']) as c:
            for x, y, cnt in c:
                pts.append((x, y, cnt))
        chk(u'交点-1个', len(pts) == 1, u'%s' % pts)
        if pts:
            chk(u'交点-坐标', abs(pts[0][0] - (X0 + 4500)) < 0.01 and
                abs(pts[0][1] - (Y0 + 2500)) < 0.01,
                u'(%.1f, %.1f)' % (pts[0][0], pts[0][1]))
    except Exception:
        traceback.print_exc()
        chk(u'交点校验', False, u'异常')

    if not sa:
        return

    # 10) 中心线：主线 ~2400（河道长 2400）；端部毛刺会抬高总长，另记
    try:
        total = 0.0
        longest = 0.0
        n = 0
        with arcpy.da.SearchCursor(G + u'\\中心线', ['SHAPE@']) as c:
            for (g,) in c:
                total += g.length
                longest = max(longest, g.length)
                n += 1
        chk(u'中心线-有条数', n >= 1, u'%d 条' % n)
        chk(u'中心线-主线长~2400', 2000 < longest < 2800,
            u'最长 %.0f 期望 ~2400' % longest)
        chk(u'中心线-总长合理', total < 4000,
            u'总长 %.0f（含端部毛刺）' % total)
    except Exception:
        traceback.print_exc()
        chk(u'中心线校验', False, u'异常')

    # 11) 河道坡度：有效栅格，均值 0~10 度
    try:
        r = arcpy.Raster(os.path.join(TMP, 'ch_slope.tif'))
        arr = arcpy.RasterToNumPyArray(r, nodata_to_value=-1)
        valid = arr[arr >= 0]
        chk(u'河道坡度-有有效格', valid.size > 1000, u'%d 格' % valid.size)
        mean = float(valid.mean())
        chk(u'河道坡度-均值范围', 0 < mean < 10,
            u'均值 %.2f°（横坡 0.08→4.57°，纵坡→0.17°）' % mean)
    except Exception:
        traceback.print_exc()
        chk(u'河道坡度校验', False, u'异常')

    # 12) 横断面测点：27 个（3 断面 x 9 点），Z 与 DEM 公式一致
    try:
        rows = []
        with arcpy.da.SearchCursor(G + u'\\测点', ['SEQ', 'DIST', 'POINT_Z']) as c:
            for seq, dist, z in c:
                rows.append((_u2(seq), dist, z))
        chk(u'测点-27个', len(rows) == 27, u'%d 期望 27' % len(rows))
        bad = 0
        with arcpy.da.SearchCursor(G + u'\\测点', ['POINT_X', 'POINT_Y', 'POINT_Z']) as c:
            for px, py, z in c:
                cc = int((px - X0) / CELL)
                rr = int((Y0 + 3000 - py) / CELL)
                exp = 100.0 + 0.003 * (cc * CELL) + 0.08 * (abs(rr - 50) * CELL)
                if z is None or abs(z - exp) > 0.01:
                    bad += 1
        chk(u'测点-Z与DEM一致', bad == 0, u'%d 个不匹配' % bad)
    except Exception:
        traceback.print_exc()
        chk(u'测点校验', False, u'异常')

    # 13) 去趋势：谷底中段值 ~0
    try:
        r = arcpy.Raster(os.path.join(TMP, 'detrend.tif'))
        arr = arcpy.RasterToNumPyArray(r)
        # 采样谷底 5 个位置（行 50，列 30/40/50/60/70）
        vals = []
        for cidx in (30, 40, 50, 60, 70):
            vals.append(float(arr[50, cidx]))
        chk(u'去趋势-谷底近零', all(abs(v) < 5.0 for v in vals),
            u'%s（期望 |v|<5）' % [round(v, 2) for v in vals])
        # 远离谷底处应显著为正（山坡）
        far = float(arr[10, 50])
        chk(u'去趋势-山坡为正', far > 50, u'%.1f 期望 >50（40行x30mx0.08=96）' % far)
    except Exception:
        traceback.print_exc()
        chk(u'去趋势校验', False, u'异常')

    # 14) 水面范围：宽 ~270m（9 行 x 30m），面积 40万~120万
    try:
        n = int(arcpy.GetCount_management(G + u'\\水面面').getOutput(0))
        total = 0.0
        with arcpy.da.SearchCursor(G + u'\\水面面', ['SHAPE@']) as c:
            for (g,) in c:
                total += g.area
        width = total / 3000.0
        chk(u'水面-连通面数', n >= 1, u'%d 个' % n)
        chk(u'水面-宽度~270', 150 < width < 450,
            u'面积 %.0f → 折算宽 %.0f m（阈值10m/坡0.08→125m半宽）' % (total, width))
    except Exception:
        traceback.print_exc()
        chk(u'水面校验', False, u'异常')


def _blob(v):
    """da 游标读回的 BLOB（py2 是 memoryview）统一转字节串。"""
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, (bytearray, memoryview)):
        return str(bytearray(v))
    return str(v)


def _u2(v):
    if isinstance(v, unicode):
        return v
    for enc in ('mbcs', 'utf-8', 'gbk'):
        try:
            return v.decode(enc)
        except Exception:
            continue
    return unicode(v)


if __name__ == '__main__':
    main()
