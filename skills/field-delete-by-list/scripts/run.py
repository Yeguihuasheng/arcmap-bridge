# -*- coding: utf-8 -*-
"""
按清单批量删除字段 —— ArcMap 版

读取一份「要素类,字段」清单（CSV），按清单把 GDB 中多个要素类的指定字段批量删除。适用于入库前清理冗余字段（如系统自动生成的Shape_Length/Shape_Area/OBJECTID 之外的废弃列）。

参数顺序（按地理处理工具原定义）：
  1. 目标地理数据库（或含要素类的工作空间）
  2. 清单 CSV（每行：要素类名,字段名；可多行同要素类）

用法：
    python run.py <目标地理数据库（或含要素类的工作空间）> <清单 CSV（每行：要素类名,字段名；可多行同要素类）>
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
    return [p.strip() for p in t.replace(u',', u';').split(u';') if p.strip()]




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
        print(u"用法: python run.py <目标地理数据库（或含要素类的工作空间）> <清单 CSV（每行：要素类名,字段名；可多行同要素类）>")
        return 1
    gdb_path = argv[0]
    setting_csv = argv[1]
    if not arcpy.Exists(gdb_path):
        raise ValueError(u"工作空间不存在: %s" % gdb_path)
    if not os.path.isfile(setting_csv):
        raise ValueError(u"清单 CSV 不存在: %s" % setting_csv)

    # 解析清单：要素类 -> [字段...]
    plan = {}
    for line in open(setting_csv, u'rb').read().decode(u'gbk', u'replace').splitlines():
        t = line.strip()
        if not t or t.startswith(u'#'):
            continue
        parts = [p.strip() for p in t.replace(u'\t', u',').split(u',')]
        if len(parts) < 2:
            continue
        fc, field = parts[0], parts[1]
        if not fc or not field:
            continue
        plan.setdefault(fc, [])
        if field not in plan[fc]:
            plan[fc].append(field)
    if not plan:
        raise ValueError(u"清单里没有读到任何「要素类,字段」行")

    arcpy.env.workspace = gdb_path
    done = 0
    skipped = 0
    for fc, fields in plan.items():
        # 定位要素类（可能直接在工作空间，也可能在要素数据集内）
        fc_path = os.path.join(gdb_path, fc)
        if not arcpy.Exists(fc_path):
            # 尝试在要素数据集里找
            found = None
            for ds in arcpy.ListDatasets():
                p = os.path.join(gdb_path, ds, fc)
                if arcpy.Exists(p):
                    found = p
                    break
            if not found:
                print(u"  跳过：找不到要素类 %s" % fc)
                skipped += 1
                continue
            fc_path = found
        existing = set(f.name.upper() for f in arcpy.ListFields(fc_path))
        for field in fields:
            if field.upper() not in existing:
                print(u"  跳过：%s 没有字段 %s" % (fc, field))
                skipped += 1
                continue
            try:
                arcpy.DeleteField_management(fc_path, field)
                print(u"  删除：%s / %s" % (fc, field))
                done += 1
            except Exception as e:
                print(u"  失败：%s / %s : %s" % (fc, field, _u(e)))
                skipped += 1
    print(u"完成：删除 %d 个字段，跳过/失败 %d 个" % (done, skipped))
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
