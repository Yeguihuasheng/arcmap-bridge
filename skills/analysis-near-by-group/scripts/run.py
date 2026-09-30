# -*- coding: utf-8 -*-
"""
按分组求组内最近要素距离 —— ArcMap 版

按一个或多个分组字段把输入要素拆成若干组，逐组只在本组内做近邻分析，把最近要素的 OID、距离、来源图层写回输入要素。用于"同村内各图斑到最近居民点的距离""同流域内各站点到最近水文站的距离"这类必须限定在同组内部比较的场景。

参数顺序（按地理处理工具原定义）：
  1. 输入要素（会被原地写入结果字段）
  2. 分组字段（多个用分号分隔）
  3. 近邻要素（多个用分号分隔）
  4. 搜索半径（可选，留空或 # 表示不限）

用法：
    python run.py <输入要素（会被原地写入结果字段）> <分组字段（多个用分号分隔）> <近邻要素（多个用分号分隔）> <搜索半径（可选，留空或 # 表示不限）>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import arcpy


try:
    _NUM_TYPES = (int, long, float)
except NameError:
    _NUM_TYPES = (int, float)


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


def _build_where(ds, fields, values):
    parts = []
    for f, v in zip(fields, values):
        fd = arcpy.AddFieldDelimiters(ds, f)
        if isinstance(v, _NUM_TYPES) and not isinstance(v, bool):
            parts.append(u"%s = %s" % (fd, v))
        else:
            parts.append(u"%s = '%s'" % (fd, _u(v).replace(u"'", u"''")))
    return u" AND ".join(parts)


def near_by_group(in_features, group_fields, near_features, search_radius):
    if arcpy.ProductInfo().lower() != 'arcinfo':
        raise RuntimeError(u"需要 ArcGIS Desktop Advanced（ArcInfo）许可")

    uniq = []
    seen = set()
    for row in arcpy.da.SearchCursor(in_features, group_fields):
        key = tuple(_u(v) for v in row)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(row)

    field_defs = [("NEAR_OID", "LONG"), ("NEAR_DISTN", "DOUBLE")]
    for fname, ftype in field_defs:
        if not _has_field(in_features, fname):
            arcpy.AddField_management(in_features, fname, ftype)
    if not _has_field(in_features, "NEAR_FCLS"):
        arcpy.AddField_management(in_features, "NEAR_FCLS", "TEXT", "", "", 255)

    arcpy.MakeFeatureLayer_management(in_features, "nbg_input_lyr")
    near_lyrs = []
    for i, nf in enumerate(near_features):
        name = u"nbg_near_%d" % i
        arcpy.MakeFeatureLayer_management(nf, name)
        near_lyrs.append(name)

    radius = search_radius if (search_radius and search_radius.strip()
                               and search_radius.strip() != u'#') else ""

    total = len(uniq)
    done = 0
    for vals in uniq:
        expr = _build_where(in_features, group_fields, vals)
        arcpy.SelectLayerByAttribute_management("nbg_input_lyr", "NEW_SELECTION", expr)
        if int(arcpy.GetCount_management("nbg_input_lyr").getOutput(0)) == 0:
            continue
        for ly in near_lyrs:
            arcpy.SelectLayerByAttribute_management(ly, "NEW_SELECTION", expr)
        arcpy.Near_analysis("nbg_input_lyr", near_lyrs, radius)

        arcpy.CalculateField_management("nbg_input_lyr", "NEAR_OID",
                                        "!NEAR_FID!", "PYTHON")
        arcpy.CalculateField_management("nbg_input_lyr", "NEAR_DISTN",
                                        "!NEAR_DIST!", "PYTHON")
        if len(near_lyrs) > 1:
            code = ("def getpath(layer):\\n"
                    "    try:\\n"
                    "        return arcpy.Describe(str(layer)).catalogPath\\n"
                    "    except:\\n"
                    "        return 'None'")
            arcpy.CalculateField_management("nbg_input_lyr", "NEAR_FCLS",
                                            "getpath(!NEAR_FC!)", "PYTHON", code)
        else:
            src_path = arcpy.Describe(near_features[0]).catalogPath
            arcpy.CalculateField_management(
                "nbg_input_lyr", "NEAR_FCLS",
                u'"%s"' % src_path.replace(u'"', u''), "PYTHON")
        done += 1
        if done % 10 == 0 or done == total:
            print(u"  已处理 %d/%d 组" % (done, total))

    for f in ("NEAR_FID", "NEAR_DIST", "NEAR_FC"):
        if _has_field(in_features, f):
            try:
                arcpy.DeleteField_management(in_features, f)
            except Exception:
                pass
    return done




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
        print(u"用法: python run.py <输入要素（会被原地写入结果字段）> <分组字段（多个用分号分隔）> <近邻要素（多个用分号分隔）> <搜索半径（可选，留空或 # 表示不限）>")
        return 1
    in_features = argv[0]
    group_fields = argv[1]
    near_features = argv[2]
    search_radius = argv[3]
    arcpy.env.overwriteOutput = True
    gf = _split(group_fields)
    nf = _split(near_features)
    if not gf:
        raise ValueError(u"分组字段不能为空")
    if not nf:
        raise ValueError(u"近邻要素不能为空")
    for f in gf:
        if not _has_field(in_features, f):
            raise ValueError(u"输入要素里没有分组字段: %s" % f)
    cnt = int(arcpy.GetCount_management(in_features).getOutput(0))
    n = near_by_group(in_features, gf, nf, search_radius)
    print(u"共 %d 个分组处理完成，结果写回: %s（要素数 %d）" % (n, in_features, cnt))
    print(u"新增字段: NEAR_OID / NEAR_DISTN / NEAR_FCLS")
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
