# -*- coding: utf-8 -*-
"""
填洼并生成 D8 流向与汇流累积 —— ArcMap 版

对 DEM 依次做填洼（Fill）→ D8 流向（Flow Direction）→汇流累积（Flow Accumulation），一次产出后续流域分析需要的两张基础栅格。是 `hydro-watershed-by-point` 的前置步骤。

参数顺序（按地理处理工具原定义）：
  1. 输入 DEM 栅格
  2. 输出位置（文件夹或地理数据库）

用法：
    python run.py <输入 DEM 栅格> <输出位置（文件夹或地理数据库）>
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
    return [p.strip() for p in t.split(u';') if p.strip()]


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
    if len(argv) < 2:
        print(u"用法: python run.py <输入 DEM 栅格> <输出位置（文件夹或地理数据库）>")
        return 1
    dem = argv[0]
    out_workspace = argv[1]
    if arcpy.CheckExtension('spatial') != 'Available':
        raise RuntimeError(u"需要 Spatial Analyst 扩展许可")
    arcpy.CheckOutExtension('spatial')
    try:
        arcpy.env.overwriteOutput = True
        ws = out_workspace
        is_gdb = ws.lower().endswith(u'.gdb')
        if not is_gdb and arcpy.Exists(ws):
            try:
                d = arcpy.Describe(ws)
                is_gdb = d.dataType in (u'Workspace', u'FeatureDataset')
            except Exception:
                pass
        if is_gdb:
            p_fdr = os.path.join(ws, u'flow_direction_d8')
            p_fac = os.path.join(ws, u'flow_accumulation_d8')
        else:
            if not os.path.isdir(ws):
                os.makedirs(ws)
            p_fdr = os.path.join(ws, u'flow_direction_d8.tif')
            p_fac = os.path.join(ws, u'flow_accumulation_d8.tif')

        print(u"1/3 填洼...")
        dem_fill = arcpy.sa.Fill(dem)
        print(u"2/3 D8 流向...")
        fdr = arcpy.sa.FlowDirection(dem_fill)
        fdr.save(p_fdr)
        print(u"3/3 汇流累积...")
        fac = arcpy.sa.FlowAccumulation(fdr, "", "FLOAT")
        fac.save(p_fac)
        for p in (p_fdr, p_fac):
            try:
                arcpy.CalculateStatistics_management(p)
            except Exception:
                pass
            try:
                arcpy.BuildPyramids_management(p)
            except Exception:
                pass
        print(u"流向 -> %s" % p_fdr)
        print(u"汇流累积 -> %s" % p_fac)
        print(u"提示: 用这两张栅格跑 hydro-watershed-by-point 做流域划分")
    finally:
        arcpy.CheckInExtension('spatial')
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
