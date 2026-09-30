# -*- coding: utf-8 -*-
"""
按字段对照表合并异构要素类 —— ArcMap 版

读一张字段对照表 CSV（每行：源要素类路径、原字段名、目标字段名），先逐个把源数据投影到统一坐标系，再把每个字段按对照关系搬到目标字段名下，最后合并成一个要素类并保留 `MERGED_SRC` 记录来源路径。用于把多年/多批次/多县市字段命名不一致的成果拼成一张总表。

参数顺序（按地理处理工具原定义）：
  1. 字段对照表 CSV（feature_path,from_field_name,to_field_name）
  2. 输出合并后的要素类
  3. 目标坐标系（.prj 文件路径 / 坐标系名 / 工厂代码，如 4490）
  4. 要保留的目标字段，分号分隔（填 # 表示保留全部）

用法：
    python run.py <字段对照表 CSV（feature_path,from_field_name,to_field_name）> <输出合并后的要素类> <目标坐标系（.prj 文件路径 / 坐标系名 / 工厂代码，如 4490）> <要保留的目标字段，分号分隔（填 # 表示保留全部）>
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

def _split(text):
    t = (text or u'').strip()
    if not t or t == u'#':
        return []
    return [p.strip() for p in t.split(u';') if p.strip()]


_TYPE_OF = {'String': 'TEXT', 'Integer': 'LONG', 'SmallInteger': 'SHORT',
            'Double': 'DOUBLE', 'Single': 'FLOAT', 'Date': 'DATE',
            'Guid': 'TEXT', 'OID': 'LONG', 'Geometry': 'TEXT'}


def _gp_type(arc_type):
    return _TYPE_OF.get(arc_type, 'TEXT')


def _resolve_sr(text):
    """坐标系参数可以是 .prj 路径 / 坐标系名 / 工厂代码"""
    t = (text or '').strip()
    sr = arcpy.SpatialReference()
    if t.isdigit():
        sr.factoryCode = int(t)
        sr.create()
        return sr
    if os.path.isfile(t):
        return arcpy.SpatialReference(t)
    sr.loadFromString(t)
    return sr


def _field_map(fc):
    d = {}
    for f in arcpy.ListFields(fc):
        d[f.name.upper()] = f
    return d




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
    if len(argv) < 4:
        print(u"用法: python run.py <字段对照表 CSV（feature_path,from_field_name,to_field_name）> <输出合并后的要素类> <目标坐标系（.prj 文件路径 / 坐标系名 / 工厂代码，如 4490）> <要保留的目标字段，分号分隔（填 # 表示保留全部）>")
        return 1
    xref_csv = argv[0]
    out_fc = argv[1]
    out_sr = argv[2]
    keep_fields = argv[3]
    arcpy.env.overwriteOutput = True
    rows = read_csv_rows(xref_csv)
    if not rows:
        raise ValueError(u"对照表是空的: %s" % xref_csv)

    # 按列标题定位，兼容中英文表头
    header = [c.lower() for c in rows[0]]
    if 'feature_path' in header:
        i_fp = header.index('feature_path')
        i_ff = header.index('from_field_name') if 'from_field_name' in header else 1
        i_tf = header.index('to_field_name') if 'to_field_name' in header else 2
        body = rows[1:]
    else:
        i_fp, i_ff, i_tf = 0, 1, 2
        body = rows

    pairs = {}
    order = []
    for r in body:
        if len(r) <= max(i_fp, i_ff, i_tf):
            continue
        fp, ff, tf = r[i_fp], r[i_ff], r[i_tf]
        if not fp or not ff or not tf:
            continue
        if fp not in pairs:
            pairs[fp] = []
            order.append(fp)
        pairs[fp].append((ff, tf))

    if not order:
        raise ValueError(u"对照表里没有有效的行，请检查列名是否为 feature_path / from_field_name / to_field_name")

    sr = _resolve_sr(out_sr)
    print(u"目标坐标系: %s" % (sr.name if sr.name else out_sr))
    keep = _split(keep_fields)

    staged = []
    for i, fp in enumerate(order):
        if not arcpy.Exists(fp):
            print(u"  跳过（不存在）: %s" % fp)
            continue
        tmp = r'in_memory\mrg_%d' % i
        d = arcpy.Describe(fp)
        try:
            same = (d.spatialReference.factoryCode == sr.factoryCode
                    and d.spatialReference.name == sr.name)
        except Exception:
            same = False
        if same:
            arcpy.CopyFeatures_management(fp, tmp)
        else:
            arcpy.Project_management(fp, tmp, sr)
        print(u"  [%d/%d] %s -> %s%s" % (i + 1, len(order), d.baseName, tmp,
                                         u"" if same else u"（已投影）"))

        fmap = _field_map(tmp)
        for src_f, tgt_f in pairs[fp]:
            if src_f.upper() not in fmap:
                continue
            if src_f.upper() == tgt_f.upper():
                continue
            if tgt_f.upper() not in fmap:
                sf = fmap[src_f.upper()]
                length = sf.length if _gp_type(sf.type) == 'TEXT' else None
                try:
                    if length:
                        arcpy.AddField_management(tmp, tgt_f, _gp_type(sf.type),
                                                  "", "", min(255, int(length)))
                    else:
                        arcpy.AddField_management(tmp, tgt_f, _gp_type(sf.type))
                except Exception as e:
                    print(u"    跳过字段 %s -> %s（%s）" % (src_f, tgt_f, e))
                    continue
            try:
                arcpy.CalculateField_management(tmp, tgt_f, "!%s!" % src_f, "PYTHON")
            except Exception as e:
                print(u"    赋值失败 %s -> %s（%s）" % (src_f, tgt_f, e))

        if not _has_field(tmp, "MERGED_SRC"):
            arcpy.AddField_management(tmp, "MERGED_SRC", "TEXT", "", "", 255)
        safe = fp.replace(u'\\', u'/').replace(u'"', u'').replace(u"'", u'')
        arcpy.CalculateField_management(tmp, "MERGED_SRC", u'"%s"' % safe, "PYTHON")
        staged.append(tmp)

    if not staged:
        raise RuntimeError(u"没有任何源要素类可用，合并中止")

    arcpy.Merge_management(staged, out_fc)
    for t in staged:
        try:
            arcpy.Delete_management(t)
        except Exception:
            pass
    print(u"合并 -> %s" % out_fc)

    if keep:
        allf = _field_map(out_fc)
        drop = []
        for f in arcpy.ListFields(out_fc):
            if f.required:
                continue
            up = f.name.upper()
            if up == 'MERGED_SRC':
                continue
            if not any(k.upper() == up for k in keep):
                drop.append(f.name)
        if drop:
            arcpy.DeleteField_management(out_fc, drop)
            print(u"已裁掉非保留字段 %d 个" % len(drop))

    print(u"最终要素数: %s" % arcpy.GetCount_management(out_fc).getOutput(0))
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
