# -*- coding: utf-8 -*-
"""第八批 7 个技能的冒烟测试（ArcMap py2.7，exec 独立 namespace 加载）。

测试数据全部造在纯 ASCII 路径 C:\\wtmp\\yghs_b8 下。
重点数值校验：
  * 四参数坐标转换：反算参数与真值（DX=100 DY=200 k=1.0 旋转30°）吻合，转换坐标精确
  * 渔网格网：3 行 4 列 = 12 个单元
  * GPX 导入：3 个 waypoint -> 3 个点
  * 按分区拆分：2 个分区各得正确点数
  * 按清单删字段：目标字段被删、保留字段仍在
  * 压缩 / 转 MDB：GDB 体积回收、MDB 生成且含要素类
"""
import math
import os
import sys
import traceback
import shutil

import arcpy

SKILLS = r'A:\GisProTest\.arcmapbridge\skills'
TMP = r'C:\wtmp\yghs_b8'
GDB = os.path.join(TMP, 'b8.gdb')
arcpy.env.overwriteOutput = True

SR = arcpy.SpatialReference(3857)

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


def build_data():
    print('===== 造测试数据 =====')
    if os.path.isdir(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP)
    arcpy.CreateFileGDB_management(TMP, 'b8.gdb')
    arcpy.env.workspace = GDB

    # 1) 供压缩 / 转 MDB / 拆分的点要素类（横跨两个分区 x<1000 与 x>=1000）
    pts = []
    for i in range(40):
        x = 500.0 + i * 40.0          # 500 ~ 2060，跨 x=1000
        y = 500.0 + (i % 5) * 100.0
        pts.append([arcpy.PointGeometry(arcpy.Point(x, y), SR)])
    mk_fc(GDB + u'\\pts', 'POINT', [], pts)

    # 2) 分区面：A(0~1000) 与 B(1000~2000)
    def poly(x0, x1):
        arr = arcpy.Array([arcpy.Point(x0, 0), arcpy.Point(x1, 0),
                           arcpy.Point(x1, 3000), arcpy.Point(x0, 3000),
                           arcpy.Point(x0, 0)])
        return arcpy.Polygon(arr, SR)
    mk_fc(GDB + u'\\frames', 'POLYGON', [(u'Name', 'TEXT')],
          [[poly(0, 1000), u'A'], [poly(1000, 2000), u'B']])

    # 3) 供删字段的要素类
    mk_fc(GDB + u'\\feat', 'POINT', [(u'Name', 'TEXT'), (u'Note', 'TEXT'),
                                     (u'Keep', 'TEXT')],
          [[arcpy.PointGeometry(arcpy.Point(0, 0), SR), u'n1', u'drop', u'keep']])

    # 4) 供四参数转换的点要素类（含原点与两个已知点）
    mk_fc(GDB + u'\\ctrl_src', 'POINT', [],
          [[arcpy.PointGeometry(arcpy.Point(0, 0), SR)],
           [arcpy.PointGeometry(arcpy.Point(1000, 0), SR)],
           [arcpy.PointGeometry(arcpy.Point(0, 1000), SR)]])

    # 5) 控制点 CSV（已知四参数 DX=100 DY=200 k=1 旋转30°）
    #    X' = 100 + 0.8660254*X - 0.5*Y ; Y' = 200 + 0.5*X + 0.8660254*Y
    b, c = math.cos(math.radians(30.0)), math.sin(math.radians(30.0))
    ctrl = [(0, 0), (1000, 0), (0, 1000), (1000, 1000), (2000, 500)]
    with open(os.path.join(TMP, 'ctrl.csv'), 'w') as fh:
        fh.write('# sx,sy,tx,ty\n')
        for sx, sy in ctrl:
            tx = 100.0 + b * sx - c * sy
            ty = 200.0 + c * sx + b * sy
            fh.write('%.6f,%.6f,%.6f,%.6f\n' % (sx, sy, tx, ty))

    # 6) GPX 文件（3 个 waypoint）
    runs_dir = os.path.join(TMP, 'runs')
    os.makedirs(runs_dir)
    with open(os.path.join(runs_dir, 'a.gpx'), 'w') as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        fh.write('<gpx version="1.1" creator="t" xmlns="http://www.topografix.com/GPX/1/1">\n')
        for i in range(3):
            fh.write('  <wpt lat="39.%d" lon="116.%d"><name>p%d</name></wpt>\n' % (i, i, i))
        fh.write('</gpx>\n')

    # 7) 供转 MDB 的独立小 GDB（放独立目录，避免污染压缩/拆分扫描范围）
    srcs_dir = os.path.join(TMP, 'srcs')
    os.makedirs(srcs_dir)
    arcpy.CreateFileGDB_management(srcs_dir, 'src.gdb')
    mk_fc(os.path.join(srcs_dir, 'src.gdb', 'a_fc'), 'POINT', [],
          [[arcpy.PointGeometry(arcpy.Point(1, 1), SR)]])

    print(u'测试数据就绪: %s' % TMP)


def main():
    build_data()
    print('===== 开始测试 =====')

    # 1) 压缩 GDB
    run(u'批量压缩GDB', 'gdb-compact', [TMP])

    # 2) 四参数：只求参数
    run(u'四参数-求参', 'coord-four-parameter',
        [os.path.join(TMP, 'ctrl.csv'), u'#', u'#',
         os.path.join(TMP, 'param_report.txt')])
    # 2b) 四参数：求参 + 转换要素类
    run(u'四参数-转换', 'coord-four-parameter',
        [os.path.join(TMP, 'ctrl.csv'), GDB + u'\\ctrl_src',
         GDB + u'\\ctrl_out', os.path.join(TMP, 'param_report2.txt')])

    # 3) 按分区拆分 GDB
    run(u'按分区拆分GDB', 'gdb-split-by-frame',
        [GDB, GDB + u'\\frames', u'Name', os.path.join(TMP, 'split_out')])

    # 4) 按清单删字段
    with open(os.path.join(TMP, 'delfields.csv'), 'w') as fh:
        fh.write('# fc,field\n')
        fh.write('feat,Note\n')
    run(u'按清单删字段', 'field-delete-by-list',
        [GDB, os.path.join(TMP, 'delfields.csv')])

    # 5) GDB 转 MDB（只扫独立 srcs 目录）
    run(u'GDB转MDB', 'gdb-to-mdb',
        [os.path.join(TMP, 'srcs'), os.path.join(TMP, 'mdb_out')])

    # 6) GPX 转要素类
    run(u'GPX转要素类', 'gpx-to-features',
        [os.path.join(TMP, 'runs'), os.path.join(TMP, 'gpx_out.gdb'), u'true'])

    # 7) 渔网格网
    run(u'渔网格网', 'geom-create-fishnet',
        [os.path.join(TMP, 'fishnet.shp'), u'0 0', u'0 10', u'0', u'0',
         u'3', u'4', u'400 300', u'NO_LABELS', u'POLYGON', u'#', u'3857'])

    print('===== 结果: PASS %d / FAIL %d =====' % (len(PASS), len(FAIL)))
    for f in FAIL:
        print(u'  FAIL: %s' % f)

    numeric_checks()
    print('===== 数值校验: OK %d / BAD %d =====' % (CHK_OK[0], CHK_BAD[0]))


def numeric_checks():
    print('===== 数值校验 =====')

    # 1) 四参数反算参数
    try:
        txt = open(os.path.join(TMP, 'param_report.txt'), 'rb').read().decode('utf-8')
        import re
        dx = float(re.search(ur'DX\s*=\s*(-?[\d.]+)', txt).group(1))
        dy = float(re.search(ur'DY\s*=\s*(-?[\d.]+)', txt).group(1))
        k = float(re.search(ur'k\s*=\s*(-?[\d.]+)', txt).group(1))
        th = float(re.search(ur'theta\s*=\s*(-?[\d.]+)', txt).group(1))
        chk(u'四参数-DX', abs(dx - 100.0) < 0.01, u'%.4f 期望 100' % dx)
        chk(u'四参数-DY', abs(dy - 200.0) < 0.01, u'%.4f 期望 200' % dy)
        chk(u'四参数-k', abs(k - 1.0) < 0.001, u'%.6f 期望 1.0' % k)
        chk(u'四参数-旋转角', abs(th - 30.0) < 0.01, u'%.4f 期望 30' % th)
    except Exception:
        traceback.print_exc()
        chk(u'四参数求参', False, u'异常')

    # 2) 四参数转换坐标（原点 (0,0) -> (100,200)）
    try:
        got = {}
        with arcpy.da.SearchCursor(GDB + u'\\ctrl_out', ['SHAPE@XY']) as c:
            for (x, y), in c:
                got[(round(x), round(y))] = 1
        chk(u'四参数-原点转换', (100, 200) in got,
            u'含 (100,200)? %s' % (sorted(got.keys())[:6]))
        chk(u'四参数-转换点数', len(got) == 3, u'%d 期望 3' % len(got))
    except Exception:
        traceback.print_exc()
        chk(u'四参数转换', False, u'异常')

    # 3) 按分区拆分：A 与 B 各得正确点数
    try:
        a_n = int(arcpy.GetCount_management(
            os.path.join(TMP, 'split_out', 'A.gdb', 'pts')).getOutput(0))
        b_n = int(arcpy.GetCount_management(
            os.path.join(TMP, 'split_out', 'B.gdb', 'pts')).getOutput(0))
        # pts: x = 500 + i*40, i=0..39 -> x 500~2060；
        # A区[0,1000] i=0..12（13 个）；B区[1000,2000] i=13..37（25 个，x=2020/2060 越界被裁）
        chk(u'拆分-A区点数', a_n == 13, u'%d 期望 13' % a_n)
        chk(u'拆分-B区点数', b_n == 25, u'%d 期望 25' % b_n)
    except Exception:
        traceback.print_exc()
        chk(u'按分区拆分', False, u'异常')

    # 4) 删字段：Note 没了，Keep 还在
    try:
        names = set(f.name for f in arcpy.ListFields(GDB + u'\\feat'))
        chk(u'删字段-Note已删', u'Note' not in names, u'%s' % sorted(names))
        chk(u'删字段-Keep保留', u'Keep' in names, u'')
        chk(u'删字段-Name保留', u'Name' in names, u'')
    except Exception:
        traceback.print_exc()
        chk(u'删字段', False, u'异常')

    # 5) GDB 转 MDB：MDB 存在且含要素类
    try:
        mdb = os.path.join(TMP, 'mdb_out', 'src.mdb')
        exists = arcpy.Exists(mdb)
        chk(u'转MDB-文件存在', exists, u'')
        if exists:
            arcpy.env.workspace = mdb
            fcs = arcpy.ListFeatureClasses()
            chk(u'转MDB-含要素类', fcs and 'a_fc' in fcs, u'%s' % (fcs or []))
    except Exception:
        traceback.print_exc()
        chk(u'GDB转MDB', False, u'异常')

    # 6) GPX 转要素类：3 个点
    try:
        n = int(arcpy.GetCount_management(
            os.path.join(TMP, 'gpx_out.gdb', 'a')).getOutput(0))
        chk(u'GPX-点数', n == 3, u'%d 期望 3' % n)
    except Exception:
        traceback.print_exc()
        chk(u'GPX转要素类', False, u'异常')

    # 7) 渔网格网：3x4 = 12 单元
    try:
        n = int(arcpy.GetCount_management(os.path.join(TMP, 'fishnet.shp')).getOutput(0))
        chk(u'渔网-单元数', n == 12, u'%d 期望 12' % n)
    except Exception:
        traceback.print_exc()
        chk(u'渔网格网', False, u'异常')


if __name__ == '__main__':
    main()
