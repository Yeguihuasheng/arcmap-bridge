# -*- coding: utf-8 -*-
"""
Landsat 波段 DN 值转辐射率与反射率 —— ArcMap 版

按 Landsat Level-1 元数据文件（_MTL.txt）把各波段 DN 值先换算成辐射率（Radiance），再按日地距离、太阳高度角与大气外太阳辐照度（ESUN）换算成表观反射率（Reflectance）。支持 Landsat 7 ETM+ / 5 TM / 4 TM 的多套 ESUN 标准。是植被指数、水体指数等定量遥感的前置步骤。

参数顺序（按地理处理工具原定义）：
  1. 波段影像所在目录（输出也放这里）
  2. 元数据文件路径（_MTL.txt，Level-1 格式）
  3. ESUN 标准：ETM+ Thuillier / ETM+ ChKur / LPS ACAA Algorithm / Landsat 5 ChKur / Landsat 4 ChKur
  4. 是否保留中间辐射率栅格：true / false
  5. 反射率缩放系数（如 1000 存整型，1 存浮点）
  6. 要处理的波段号，分号分隔（如 1;2;3;4;5;7）

用法：
    python run.py <波段影像所在目录（输出也放这里）> <元数据文件路径（_MTL.txt，Level-1 格式）> <ESUN 标准：ETM+ Thuillier / ETM+ ChKur / LPS ACAA Algorithm / Landsat 5 ChKur / Landsat 4 ChKur> <是否保留中间辐射率栅格：true / false> <反射率缩放系数（如 1000 存整型，1 存浮点）> <要处理的波段号，分号分隔（如 1;2;3;4;5;7）>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import math
import time
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

def _read_metadata(path):
    """解析 _MTL.txt：key = value 行，END 截止。"""
    md = {}
    with open(path, u'r') as f:
        for line in f:
            if not line.strip() == u'END':
                val = line.strip().split(u'=')
                if len(val) >= 2:
                    md[val[0].strip()] = val[1].strip().strip(u'"')
            else:
                break
    return md


def _meta_keys(md, band):
    """兼容 Landsat7 新/老两种元数据字段名。"""
    b = u'%s' % band
    if u'RADIANCE_MAXIMUM_BAND_' + b in md:
        return [u'FILE_NAME_BAND_' + b, u'RADIANCE_MAXIMUM_BAND_' + b,
                u'RADIANCE_MINIMUM_BAND_' + b,
                u'QUANTIZE_CAL_MAX_BAND_' + b,
                u'QUANTIZE_CAL_MIN_BAND_' + b, u'DATE_ACQUIRED']
    if u'LMAX_BAND' + b in md:
        return [u'BAND' + b + u'_FILE_NAME', u'LMAX_BAND' + b,
                u'LMIN_BAND' + b, u'QCALMAX_BAND' + b,
                u'QCALMIN_BAND' + b, u'ACQUISITION_DATE']
    raise ValueError(u'_MTL.txt 不是可识别的 Level-1 格式（波段 %s 字段缺失）' % b)


def _jday(date_str):
    dt = date_str.rsplit(u'-')
    t = time.mktime((int(dt[0]), int(dt[1]), int(dt[2]), 0, 0, 0, 0, 0, 0))
    return time.gmtime(t)[7]


def _solar_dist(jday, d_csv):
    """按儒略日查日地距离（天文单位）。resources/d.csv 随技能打包。"""
    with open(d_csv, u'r') as f:
        lines = f.readlines()[2:]
    dists = [float(l.strip().split(u',')[1]) for l in lines if l.strip()]
    return dists[int(jday) - 1]


def _esun(band, si_type):
    if si_type == u'ETM+ Thuillier':
        es = {u'1': 1997, u'2': 1812, u'3': 1533, u'4': 1039, u'5': 230.8,
              u'7': 84.90, u'8': 1362}
    elif si_type == u'ETM+ ChKur':
        es = {u'1': 1970, u'2': 1842, u'3': 1547, u'4': 1044, u'5': 225.7,
              u'7': 82.06, u'8': 1369}
    elif si_type == u'LPS ACAA Algorithm':
        es = {u'1': 1969, u'2': 1840, u'3': 1551, u'4': 1044, u'5': 225.7,
              u'7': 82.06, u'8': 1368}
    elif si_type == u'Landsat 5 ChKur':
        es = {u'1': 1957, u'2': 1825, u'3': 1557, u'4': 1033, u'5': 214.9,
              u'7': 80.72}
    elif si_type == u'Landsat 4 ChKur':
        es = {u'1': 1957, u'2': 1826, u'3': 1554, u'4': 1036, u'5': 215,
              u'7': 80.67}
    else:
        raise ValueError(u'si_type 只能是 5 套标准之一: %s' % si_type)
    b = u'%s' % band
    if b not in es:
        raise ValueError(u'标准 %s 里没有波段 %s 的 ESUN 值' % (si_type, b))
    return es[b]




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
    if len(argv) < 6:
        print(u"用法: python run.py <波段影像所在目录（输出也放这里）> <元数据文件路径（_MTL.txt，Level-1 格式）> <ESUN 标准：ETM+ Thuillier / ETM+ ChKur / LPS ACAA Algorithm / Landsat 5 ChKur / Landsat 4 ChKur> <是否保留中间辐射率栅格：true / false> <反射率缩放系数（如 1000 存整型，1 存浮点）> <要处理的波段号，分号分隔（如 1;2;3;4;5;7）>")
        return 1
    workspace = argv[0]
    metadata_path = argv[1]
    si_type = argv[2]
    keep_rad = argv[3]
    scale_factor = float(argv[4])
    bands = argv[5]
    if arcpy.CheckExtension(u'spatial') != u'Available':
        raise RuntimeError(u"需要 Spatial Analyst 扩展许可")
    arcpy.CheckOutExtension(u'spatial')
    try:
        arcpy.env.overwriteOutput = True
        if not os.path.isdir(workspace):
            raise ValueError(u"目录不存在: %s" % workspace)
        if not os.path.isfile(metadata_path):
            raise ValueError(u"元数据文件不存在: %s" % metadata_path)
        arcpy.env.workspace = workspace

        # d.csv 随技能打包在 resources/ 下；优先按 __file__ 定位
        # （桥/exec 方式下 sys.argv[0] 不一定是本脚本路径）
        _here = os.path.dirname(os.path.abspath(
            globals().get(u'__file__', sys.argv[0])))
        d_csv = os.path.join(_here, os.pardir, u'resources', u'd.csv')
        if not os.path.isfile(d_csv):
            d_csv = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                                 os.pardir, u'resources', u'd.csv')
        if not os.path.isfile(d_csv):
            raise RuntimeError(u"缺少随技能打包的日地距离表: %s" % d_csv)

        band_list = _split(bands)
        if not band_list:
            raise ValueError(u"至少给一个波段号")
        keep = (keep_rad or u'').strip().lower() == u'true'

        md = _read_metadata(metadata_path)
        if u'SUN_ELEVATION' not in md:
            raise ValueError(u"元数据里缺 SUN_ELEVATION")

        ok_n = 0
        for band in band_list:
            keys = _meta_keys(md, band)
            band_file, lmax, lmin, qmax, qmin, date_k = keys
            qcal = os.path.join(workspace, md[band_file])
            if not arcpy.Exists(qcal):
                print(u"  跳过（波段文件不存在）: %s" % md[band_file])
                continue

            # DN -> 辐射率
            lmax_v, lmin_v = float(md[lmax]), float(md[lmin])
            qmax_v, qmin_v = float(md[qmax]), float(md[qmin])
            gain = (lmax_v - lmin_v) / (qmax_v - qmin_v)
            inras = arcpy.sa.Raster(qcal)
            rad = (gain * (inras - qmin_v)) + lmin_v
            rad_name = u'RadianceB%s.tif' % band
            rad.save(os.path.join(workspace, rad_name))

            # 辐射率 -> 反射率
            dist = _solar_dist(_jday(md[date_k]), d_csv)
            esun = _esun(band, si_type)
            zenith = ((90.0 - float(md[u'SUN_ELEVATION'])) * math.pi) / 180.0
            refl = ((math.pi * rad * math.pow(dist, 2))
                    / (esun * math.cos(zenith))) * scale_factor
            refl_name = u'ReflectanceB%s.tif' % band
            refl.save(os.path.join(workspace, refl_name))
            if not keep:
                arcpy.Delete_management(os.path.join(workspace, rad_name))
            ok_n += 1
            print(u"  波段 %s -> %s（日地距离 %.5f AU，ESUN %s）"
                  % (band, refl_name, dist, esun))
        print(u"完成: %d/%d 个波段（缩放系数 %g）"
              % (ok_n, len(band_list), scale_factor))
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
