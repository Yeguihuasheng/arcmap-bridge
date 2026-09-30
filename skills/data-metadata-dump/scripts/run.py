# -*- coding: utf-8 -*-
"""
跨目录递归盘点要素类与字段结构 —— ArcMap 版

递归扫一个根目录（含嵌套的 .gdb / .mdb / .shp），把找到的每个要素类登记成一张要素级表（路径、名称、几何类型、要素数、坐标系、四至范围），再逐字段登记成一张字段级表（别名、类型、长度、精度、小数位、是否可空、是否必填）。两张 CSV 用 UUID 关联，用于接手陌生数据时的整体盘库与结构备案。

参数顺序（按地理处理工具原定义）：
  1. 要递归扫描的根目录
  2. 输出 CSV 的目录
  3. 输出文件名前缀（默认 metadata_dump）
  4. 数据源类型，分号分隔（.shp;.gdb;.mdb；填 # 表示全部）
  5. 要素类型，分号分隔（Polygon;Polyline;Point；填 # 表示全部）

用法：
    python run.py <要递归扫描的根目录> <输出 CSV 的目录> <输出文件名前缀（默认 metadata_dump）> <数据源类型，分号分隔（.shp;.gdb;.mdb；填 # 表示全部）> <要素类型，分号分隔（Polygon;Polyline;Point；填 # 表示全部）>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import csv
import re
import arcpy


def _s(v):
    """任意值转 unicode 文本（py2/py3 通用，中文安全）"""
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


def _enc(v):
    """CSV 写出前的编码：py2 的 csv 模块不接受 unicode，必须编码成字节。"""
    s = _s(v)
    if sys.version_info[0] < 3:
        return s.encode('utf-8')
    return s


def _dec(v):
    """CSV 读出的字节：utf-8 优先（与 _enc 自洽），失败再退到系统编码。"""
    if isinstance(v, bytes):
        for enc in ('utf-8', 'mbcs', 'gbk', 'latin-1'):
            try:
                return v.decode(enc)
            except Exception:
                continue
        return v.decode('utf-8', 'replace')
    return u'%s' % v


def write_csv(path, header, rows):
    """写 CSV：py2 走二进制模式，py3 走文本模式 + utf-8-sig（Excel 可直接开）"""
    if sys.version_info[0] >= 3:
        import io as _io
        fh = _io.open(path, 'w', newline='', encoding='utf-8-sig')
    else:
        fh = open(path, 'wb')
    try:
        w = csv.writer(fh)
        w.writerow([_enc(h) for h in header])
        for r in rows:
            w.writerow([_enc(c) for c in r])
    finally:
        fh.close()
    return path


def read_csv_rows(path):
    """读 CSV 为 unicode 行列表；自动跳过含中文表头的首行"""
    if sys.version_info[0] >= 3:
        import io as _io
        fh = _io.open(path, 'r', newline='', encoding='utf-8-sig')
        rd = csv.reader(fh)
    else:
        fh = open(path, 'rb')
        rd = csv.reader(fh)
    try:
        rows = []
        for r in rd:
            if not r:
                continue
            rows.append([_dec(c).strip() for c in r])
    finally:
        fh.close()
    return rows


def _has_field(ds, name):
    for f in arcpy.ListFields(ds):
        if f.name.upper() == name.upper():
            return True
    return False

def _walk_feats(root_dir, src_types, shape_types):
    """递归遍历根目录，找出 shp / gdb / mdb 里的要素类。

    src_types  : ['.shp', '.gdb', '.mdb'] 的子集，空列表=全部
    shape_types: ['Polygon', 'Polyline', 'Point', 'Multipoint', 'MultiPatch'] 的子集，空=全部
    """
    feats = []

    def _in_ws(wksp):
        old = arcpy.env.workspace
        arcpy.env.workspace = wksp
        out = []
        try:
            for fc in arcpy.ListFeatureClasses():
                out.append(arcpy.Describe(fc).catalogPath)
            for fds in (arcpy.ListDatasets('', 'Feature') or []):
                arcpy.env.workspace = os.path.join(wksp, fds)
                for fc in arcpy.ListFeatureClasses():
                    out.append(arcpy.Describe(fc).catalogPath)
        except Exception:
            pass
        finally:
            arcpy.env.workspace = old
        return out

    want_shp = (not src_types) or ('.shp' in src_types)
    want_gdb = (not src_types) or ('.gdb' in src_types)
    want_mdb = (not src_types) or ('.mdb' in src_types)

    for root, dirs, files in os.walk(root_dir):
        low = root.lower()
        if want_gdb and low.endswith('.gdb'):
            feats.extend(_in_ws(root))
        if want_mdb:
            for f in files:
                if f.lower().endswith('.mdb'):
                    feats.extend(_in_ws(os.path.join(root, f)))
        if want_shp:
            for f in files:
                if f.lower().endswith('.shp'):
                    feats.append(os.path.join(root, f))

    if not shape_types:
        return feats
    out = []
    for fc in feats:
        try:
            st = arcpy.Describe(fc).shapeType
        except Exception:
            continue
        if st in shape_types:
            out.append(fc)
    return out

def _split(text):
    t = (text or u'').strip()
    if not t or t == u'#':
        return []
    return [p.strip() for p in t.split(u';') if p.strip()]


def _sr_name(fc):
    try:
        sr = arcpy.Describe(fc).spatialReference
        if sr is None:
            return u''
        return u'%s (%s)' % (sr.name, sr.factoryCode)
    except Exception:
        return u''




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
    if len(argv) < 5:
        print(u"用法: python run.py <要递归扫描的根目录> <输出 CSV 的目录> <输出文件名前缀（默认 metadata_dump）> <数据源类型，分号分隔（.shp;.gdb;.mdb；填 # 表示全部）> <要素类型，分号分隔（Polygon;Polyline;Point；填 # 表示全部）>")
        return 1
    root_dir = argv[0]
    out_dir = argv[1]
    out_prefix = argv[2]
    src_types = argv[3]
    shape_types = argv[4]
    arcpy.env.overwriteOutput = True
    if not os.path.isdir(root_dir):
        raise ValueError(u"根目录不存在: %s" % root_dir)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    prefix = (out_prefix or u'').strip() or u'metadata_dump'

    feats = _walk_feats(root_dir, _split(src_types), _split(shape_types))
    print(u"扫到要素类 %d 个" % len(feats))

    feat_rows = []
    schema_rows = []
    for i, fc in enumerate(feats):
        uid = u'F%06d' % (i + 1)
        try:
            d = arcpy.Describe(fc)
            name = d.baseName
            stype = getattr(d, 'shapeType', u'')
            ext = d.extent
            bbox = (ext.XMin, ext.YMin, ext.XMax, ext.YMax)
            cnt = int(arcpy.GetCount_management(fc).getOutput(0))
            readable = u'True'
        except Exception as e:
            name = os.path.splitext(os.path.basename(fc))[0]
            stype = u''
            bbox = (u'', u'', u'', u'')
            cnt = u''
            readable = u'False'
            print(u"  读取失败，已跳过: %s (%s)" % (fc, e))

        ws = os.path.basename(os.path.dirname(fc))
        feat_rows.append([uid, fc, name, ws, stype, cnt, _sr_name(fc),
                          bbox[0], bbox[1], bbox[2], bbox[3], readable])
        if readable != u'True':
            continue
        try:
            for f in arcpy.ListFields(fc):
                schema_rows.append([uid, name, f.name, f.aliasName, f.type,
                                    f.length, f.precision, f.scale,
                                    f.isNullable, f.required, f.defaultValue])
        except Exception as e:
            print(u"  字段读取失败: %s (%s)" % (fc, e))

    fcsv = write_csv(os.path.join(out_dir, prefix + u'_features.csv'),
                     [u'FEAT_UUID', u'路径', u'名称', u'所在库', u'几何类型',
                      u'要素数', u'坐标系', u'XMin', u'YMin', u'XMax', u'YMax',
                      u'READABLE'], feat_rows)
    scsv = write_csv(os.path.join(out_dir, prefix + u'_schema.csv'),
                     [u'FEAT_UUID', u'要素类', u'字段名', u'别名', u'类型',
                      u'长度', u'精度', u'小数位', u'可为空', u'必填', u'默认值'],
                     schema_rows)
    print(u"要素级 -> %s（%d 行）" % (fcsv, len(feat_rows)))
    print(u"字段级 -> %s（%d 行）" % (scsv, len(schema_rows)))
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
