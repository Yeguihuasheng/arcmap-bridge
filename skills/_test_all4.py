# -*- coding: utf-8 -*-
"""
skills 全面测试（py2.7，exec 独立 namespace 加载，参数用 unicode 字面量避免命令行编码问题）。
"""
import sys
import os
import traceback

sys.path.insert(0, r'A:\GisProTest\.arcmapbridge\skills')
import _common as C

GDB = r'C:\Users\Administrator\AppData\Local\Temp\yghs_skill_test.gdb'
OUTDIR = os.path.join(os.environ.get('TEMP', '.'), 'yghs_skill_out')
if not os.path.isdir(OUTDIR):
    os.makedirs(OUTDIR)

PASS = []
FAIL = []
_counter = [0]


def run(label, skill, argv):
    script = os.path.join(r'A:\GisProTest\.arcmapbridge\skills', skill, 'scripts', 'run.py')
    src = open(script, 'rb').read().decode('utf-8')
    # 去掉 coding 声明行（exec unicode 串会报）
    lines = src.splitlines()
    if lines and 'coding' in lines[0]:
        lines = lines[1:]
    src = '\n'.join(lines)
    # 独立 namespace，模块名唯一
    _counter[0] += 1
    modname = 'run_%d' % _counter[0]
    ns = {'__name__': modname, '__file__': script}
    try:
        exec(compile(src, script, 'exec'), ns)
        rc = ns['main'](*argv)
        ok = (rc in (0, None))
    except Exception:
        traceback.print_exc()
        ok = False
        rc = 'EXC'
    (PASS if ok else FAIL).append(label)
    print '%-4s [%s] rc=%s' % ('PASS' if ok else 'FAIL', label, rc)
    return ok


def main():
    print '===== skills 全面测试（exec namespace） ====='

    run('移除代码后0', 'plan-remove0-d-m', [GDB + '\\三调', 'DLBM'])
    run('代码后补0', 'plan-supply0-d-m', [GDB + '\\三调', 'DLBM', '6'])
    run('三调DLBM转DLMC', 'plan-s-d-changer', [GDB + '\\三调', 'DLBM', 'DLMC', u'DLBM转DLMC'])
    run('三调DLMC转DLBM', 'plan-s-d-changer', [GDB + '\\三调', 'DLBM', 'DLMC', u'DLMC转DLBM'])
    run('分级编码名称', 'plan-create-grad-y-d-y-h', [GDB + '\\用地用海', 'BM', '2', u'新版', u'是'])
    run('用地用海代码转名称', 'plan-y-d-y-h-changer', [GDB + '\\用地用海', 'BM', 'MC', u'代码转名称', u'新版'])
    run('用地用海旧转新', 'plan-y-d-y-h-old2-new', [GDB + '\\用地用海', 'BM', 'BM_NEW', 'MC_NEW'])
    run('三调转用地用海', 'plan-s-d2-y-d-y-h', [GDB + '\\三调', 'DLMC', 'YDYH', u'通用', u'新版'])
    run('赋值用地用海', 'plan-updata-y-d-y-h', [GDB + '\\用地用海', 'BM2', 'MC2', u'01耕地'])
    run('现状规划变化检测', 'plan-check-y-d-change', [GDB + '\\现状', GDB + '\\规划', 'DLBM', 'DLBM', OUTDIR + '\\check_result'])
    run('通用面积统计', 'plan-general-statistic', [GDB + '\\三调', 'MJ', 'DLBM', u'公顷', OUTDIR + '\\gen.csv'])
    run('智能汇总统计', 'plan-multi-statistics', [GDB + '\\分区', 'NAME', u'投影', u'公顷', OUTDIR + '\\multi.csv', GDB + '\\三调'])
    run('批量地类面积统计', 'plan-multi-statistics-y-d', [GDB + '\\分区', 'NAME', u'投影', u'公顷', OUTDIR + '\\multi_yd.csv', GDB + '\\三调', 'KCXS'])
    run('道路网密度', 'plan-statistic-load', [GDB + '\\道路', 'TYPE', GDB + '\\分区', OUTDIR + '\\road.csv'])
    run('三调三大类', 'plan-statistics-s-d-l', [GDB + '\\三调', 'DLBM', u'空', u'投影', u'公顷', OUTDIR + '\\sdl.csv'])
    run('用地用海指标汇总', 'plan-statistics-y-d-y-h', [GDB + '\\用地用海', 'BM', 'MJ', u'公顷', u'大类', OUTDIR + '\\ydyh.csv'])
    run('现状规划指标对比', 'plan-statistics-x-z-g-h', [GDB + '\\现状', GDB + '\\规划', 'DLBM', 'MJ', u'公顷', u'大类', OUTDIR + '\\xzgh.csv'])
    run('三区三线占用', 'plan-s-q-s-x-statistics', [GDB + '\\分区', 'NAME', GDB + '\\现状', GDB + '\\规划', GDB + '\\三调', u'投影', u'公顷', OUTDIR + '\\sqsx.csv'])
    run('国土地类统计', 'territory-z-y1', [u'地类统计', GDB + '\\三调', 'DLBM', u'公顷', OUTDIR + '\\zy_stat.csv', 'MJ'])
    run('国土三大类归并', 'territory-z-y1', [u'三大类归并', GDB + '\\三调', 'DLBM', u'公顷', OUTDIR + '\\zy_3.csv', 'MJ'])
    run('线转道路(降级)', 'plan-line-to-road', [GDB + '\\道路', '30', '5', GDB, u'红线', u'路缘石线', u'中心线'])
    run('道路交叉口(降级)', 'plan-create-road-intersection', [GDB + '\\道路', GDB, u'交叉口'])

    # gdb-truncate（副本）
    import arcpy
    copy_gdb = os.path.join(os.environ.get('TEMP', '.'), 'yghs_trunc_test.gdb')
    if arcpy.Exists(copy_gdb):
        arcpy.Delete_management(copy_gdb)
    arcpy.CreateFileGDB_management(os.path.dirname(copy_gdb), 'yghs_trunc_test.gdb')
    arcpy.CreateFeatureclass_management(copy_gdb, 'test', 'POINT')
    with arcpy.da.InsertCursor(copy_gdb + '\\test', ['SHAPE@XY']) as cur:
        cur.insertRow([(0, 0)])
        cur.insertRow([(1, 1)])
    run('清空GDB要素数据', 'gdb-truncate-data', [copy_gdb, u'否'])

    print '===== 汇总 ====='
    print 'PASS %d / FAIL %d / 总 %d' % (len(PASS), len(FAIL), len(PASS) + len(FAIL))
    if FAIL:
        print '失败项:', FAIL


if __name__ == '__main__':
    main()
