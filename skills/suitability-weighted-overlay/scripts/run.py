# -*- coding: utf-8 -*-
"""
加权叠加适宜性评价 —— ArcMap 版

按一张准则表把多个栅格（坡度、距离道路、辐射量、地类等）分别重分类到统一分值，再按权重加权求和得到适宜性栅格；可按"排除栅格 + 排除规则"扣掉禁建区，并按最低分值与最小连片像元数圈出候选地块。用于光伏选址、设施农用地选址、公共服务设施布点等"多因子打分"场景。

参数顺序（按地理处理工具原定义）：
  1. 准则表 CSV（名称,栅格路径,类型 range/value,重分类规则,权重）
  2. 输出适宜性栅格
  3. 排除栅格（可选，填 # 跳过）
  4. 排除规则（可选，如 >15 或 =11;=12；填 # 跳过）
  5. 候选地块最低分值（可选，填 # 跳过圈选）
  6. 候选地块最小连片像元数（默认 9）
  7. 输出候选地块面要素（可选，填 # 跳过）

用法：
    python run.py <准则表 CSV（名称,栅格路径,类型 range/value,重分类规则,权重）> <输出适宜性栅格> <排除栅格（可选，填 # 跳过）> <排除规则（可选，如 >15 或 =11;=12；填 # 跳过）> <候选地块最低分值（可选，填 # 跳过圈选）> <候选地块最小连片像元数（默认 9）> <输出候选地块面要素（可选，填 # 跳过）>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import csv
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

def _num(x):
    return float(_s(x).strip())


def _num_int(x):
    """整型栅格的重分类区间必须给整数，给浮点会报 ERROR 000628。

    能整除就转 int，否则保留浮点（浮点栅格用）。"""
    f = _num(x)
    i = int(f)
    if abs(f - i) < 1e-9:
        return i
    return f


def parse_remap(kind, rule):
    """把规则文本转成 sa.RemapRange / sa.RemapValue"""
    items = []
    for seg in _s(rule).split(u';'):
        seg = seg.strip()
        if not seg:
            continue
        parts = seg.replace(u',', u' ').split()
        items.append(parts)
    if not items:
        raise ValueError(u"重分类规则为空: %s" % rule)
    if kind == u'range':
        rr = []
        for p in items:
            if len(p) != 3:
                raise ValueError(u"range 规则每项应为『下限 上限 分值』，实际: %s" % u' '.join(p))
            rr.append([_num_int(p[0]), _num_int(p[1]), _num_int(p[2])])
        return arcpy.sa.RemapRange(rr)
    if kind == u'value':
        rv = []
        for p in items:
            if len(p) != 2:
                raise ValueError(u"value 规则每项应为『原值 分值』，实际: %s" % u' '.join(p))
            v = _num(p[0])
            if v == int(v):
                v = int(v)
            rv.append([v, _num(p[1])])
        return arcpy.sa.RemapValue(rv)
    raise ValueError(u"类型只能是 range 或 value，实际: %s" % kind)


def build_exclude(raster_path, rule):
    """排除规则 -> 条件栅格；返回 None 表示不需要排除"""
    if not raster_path or raster_path.strip() == u'#':
        return None
    rule = (rule or u'').strip()
    if not rule or rule == u'#':
        return None
    exc = None
    base = None
    for seg in rule.split(u';'):
        seg = seg.strip()
        if not seg:
            continue
        if base is None:
            base = arcpy.Raster(raster_path)
        if seg.startswith(u'>'):
            e = base > _num(seg[1:])
        elif seg.startswith(u'<'):
            e = base < _num(seg[1:])
        elif seg.startswith(u'='):
            sub = None
            for v in seg[1:].split(u','):
                v = v.strip()
                if not v:
                    continue
                one = base == _num(v)
                sub = one if sub is None else (sub | one)
            if sub is None:
                continue
            e = sub
        else:
            raise ValueError(u"排除条件要以 > < = 开头，实际: %s" % seg)
        exc = e if exc is None else (exc | e)
    return exc




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
    if len(argv) < 7:
        print(u"用法: python run.py <准则表 CSV（名称,栅格路径,类型 range/value,重分类规则,权重）> <输出适宜性栅格> <排除栅格（可选，填 # 跳过）> <排除规则（可选，如 >15 或 =11;=12；填 # 跳过）> <候选地块最低分值（可选，填 # 跳过圈选）> <候选地块最小连片像元数（默认 9）> <输出候选地块面要素（可选，填 # 跳过）>")
        return 1
    criteria_csv = argv[0]
    out_suitability = argv[1]
    exclude_raster = argv[2]
    exclude_rule = argv[3]
    min_score = argv[4]
    min_cells = int(float(argv[5]))
    out_sites = argv[6]
    if arcpy.CheckExtension('spatial') != 'Available':
        raise RuntimeError(u"需要 Spatial Analyst 扩展许可")
    arcpy.CheckOutExtension('spatial')
    try:
        arcpy.env.overwriteOutput = True
        rows = read_csv_rows(criteria_csv)
        if not rows:
            raise ValueError(u"准则表是空的: %s" % criteria_csv)

        total = None
        names = []
        for r in rows:
            if len(r) < 5:
                raise ValueError(u"准则表每行要 5 列（名称,栅格,类型,规则,权重），实际: %s" % u','.join(r))
            name, ras_path, kind, rule, weight = r[0], r[1], r[2].lower(), r[3], r[4]
            if kind not in (u'range', u'value'):
                # 首行可能是中文表头，跳过
                continue
            remap = parse_remap(kind, rule)
            try:
                # 整型栅格没有属性表时重分类容易失败，先补一个
                arcpy.BuildRasterAttributeTable_management(ras_path, "Overwrite")
            except Exception:
                pass
            rc = arcpy.sa.Reclassify(ras_path, "VALUE", remap, "NODATA")
            w = _num(weight)
            print(u"  %s 权重 %.4g 已重分类" % (name, w))
            names.append(name)
            term = rc * w
            total = term if total is None else (total + term)

        if total is None:
            raise ValueError(u"准则表里没有有效的 range/value 行")

        exc = build_exclude(exclude_raster, exclude_rule)
        if exc is not None:
            total = arcpy.sa.SetNull(exc, total)
            print(u"已按排除规则扣掉禁建区")
        total.save(out_suitability)
        print(u"适宜性栅格 -> %s（参与因子: %s）" % (out_suitability, u'、'.join(names)))

        if out_sites and out_sites.strip() and out_sites.strip() != u'#':
            kept = arcpy.Raster(out_suitability)
            ms = (min_score or u'').strip()
            if ms and ms != u'#':
                kept = arcpy.sa.SetNull(kept < _num(ms), kept)
            groups = arcpy.sa.RegionGroup(
                arcpy.sa.Con(arcpy.sa.IsNull(kept) == 0, 1), "EIGHT")
            big = arcpy.sa.SetNull(groups, groups, "COUNT < %d" % max(1, min_cells))
            arcpy.RasterToPolygon_conversion(big, out_sites, "NO_SIMPLIFY", "VALUE")
            cnt = arcpy.GetCount_management(out_sites).getOutput(0)
            print(u"候选地块 -> %s（%s 个，最小连片 %d 像元）" % (out_sites, cnt, min_cells))
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
