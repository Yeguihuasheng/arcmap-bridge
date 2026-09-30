# -*- coding: utf-8 -*-
"""
生成字段对照表（源字段到目标字段） —— ArcMap 版

递归扫一个根目录里指定几何类型的要素类，把每个要素类的每个字段登记成一行，再用模糊匹配给它推荐一个目标字段名（可指定一份"目标 schema"要素类作为标准）。输出的对照表 CSV 让人在 Excel 里改完 `to_field_name` 后，交给 `data-merge-by-crossref` 按这张表把异构数据合并成一张。

参数顺序（按地理处理工具原定义）：
  1. 要递归扫描的根目录
  2. 要素类型（Polygon / Polyline / Point / Multipoint / MultiPatch）
  3. 输出对照表 CSV 路径
  4. 目标 schema 要素类或表（可选，填 # 则用全部字段互匹配）
  5. 数据源类型，分号分隔（.shp;.gdb;.mdb；填 # 表示全部）

用法：
    python run.py <要递归扫描的根目录> <要素类型（Polygon / Polyline / Point / Multipoint / MultiPatch）> <输出对照表 CSV 路径> <目标 schema 要素类或表（可选，填 # 则用全部字段互匹配）> <数据源类型，分号分隔（.shp;.gdb;.mdb；填 # 表示全部）>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import csv
import re
import difflib
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


def best_match(value, candidates):
    """在候选字段名里找最像的一个，返回 (匹配结果, 相似度)。"""
    if not candidates:
        return (u'', 0.0)
    if value in candidates:
        return (value, 1.0)
    got = difflib.get_close_matches(value, candidates, 1, 0.6)
    if not got:
        return (u'', 0.0)
    target = got[0]
    ratio = difflib.SequenceMatcher(None, value, target).ratio()
    return (target, ratio)


# 注：输出到 shapefile 时字段名会被截到 10 个字符，建议输出到文件地理数据库




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
        print(u"用法: python run.py <要递归扫描的根目录> <要素类型（Polygon / Polyline / Point / Multipoint / MultiPatch）> <输出对照表 CSV 路径> <目标 schema 要素类或表（可选，填 # 则用全部字段互匹配）> <数据源类型，分号分隔（.shp;.gdb;.mdb；填 # 表示全部）>")
        return 1
    root_dir = argv[0]
    shape_type = argv[1]
    out_csv = argv[2]
    target_schema = argv[3]
    src_types = argv[4]
    arcpy.env.overwriteOutput = True
    if not os.path.isdir(root_dir):
        raise ValueError(u"根目录不存在: %s" % root_dir)
    st = (shape_type or u'').strip()
    if not st or st == u'#':
        raise ValueError(u"要素类型必填（Polygon / Polyline / Point / Multipoint / MultiPatch）")

    feats = _walk_feats(root_dir, _split(src_types), [st])
    print(u"扫到 %s 要素类 %d 个" % (st, len(feats)))

    tgt_schema = (target_schema or u'').strip()
    candidates = []
    if tgt_schema and tgt_schema != u'#':
        for f in arcpy.ListFields(tgt_schema):
            if not f.required:
                candidates.append(f.name)
    if not candidates:
        seen = []
        for fc in feats:
            try:
                for f in arcpy.ListFields(fc):
                    if f.name not in seen and not f.required:
                        seen.append(f.name)
            except Exception:
                continue
        candidates = seen

    rows = []
    for fc in feats:
        try:
            name = arcpy.Describe(fc).baseName
            fields = [(f.name, f.type, f.length) for f in arcpy.ListFields(fc)
                      if not f.required]
        except Exception as e:
            print(u"  读取失败已跳过: %s (%s)" % (fc, e))
            continue
        for fname, ftype, flen in fields:
            tgt, ratio = best_match(fname, candidates)
            rows.append([fc, name, fname, tgt, u'%.2f' % ratio, ftype, flen])

    write_csv(out_csv,
              [u'feature_path', u'feature_name', u'from_field_name',
               u'to_field_name', u'match_ratio', u'field_type', u'field_length'],
              rows)
    print(u"对照表 -> %s（%d 行，候选目标字段 %d 个）" % (out_csv, len(rows), len(candidates)))
    print(u"提示: 在 Excel 里核完 to_field_name 后，用 data-merge-by-crossref 合并")
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
