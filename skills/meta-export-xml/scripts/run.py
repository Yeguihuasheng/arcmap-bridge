# -*- coding: utf-8 -*-
"""
批量导出元数据 XML（精确副本） —— ArcMap 版

把一批数据集的元数据按「精确副本」样式（exact copy of.xslt）逐个导出成 XML 文件，不改写同步信息。用于成果归档、元数据批量送审、把元数据转移到别的平台。

参数顺序（按地理处理工具原定义）：
  1. 数据集列表（分号分隔，要素类/表/栅格/图层均可）
  2. XML 输出目录

用法：
    python run.py <数据集列表（分号分隔，要素类/表/栅格/图层均可）> <XML 输出目录>
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


def _has_field(ds, name):
    for f in arcpy.ListFields(ds):
        if f.name.upper() == name.upper():
            return True
    return False

_BAD = u'\\/:*?"<>|'


def _safe_name(s):
    out = u''.join(u'_' if ch in _BAD else ch for ch in _u(s)).strip()
    return out or u'noname'




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
        print(u"用法: python run.py <数据集列表（分号分隔，要素类/表/栅格/图层均可）> <XML 输出目录>")
        return 1
    datasets = argv[0]
    out_dir = argv[1]
    ds_list = _split(datasets)
    if not ds_list:
        raise ValueError(u"至少给一个数据集")
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    install_dir = arcpy.GetInstallInfo().get(u'InstallDir', u'')
    xslt = os.path.join(install_dir, u'Metadata', u'Stylesheets',
                        u'gpTools', u'exact copy of.xslt')
    if not os.path.isfile(xslt):
        raise RuntimeError(u"找不到元数据样式表: %s\n"
                           u"（ArcGIS Desktop 安装不完整，缺 Metadata 组件）" % xslt)

    used = {}
    done = 0
    for ds in ds_list:
        if not arcpy.Exists(ds):
            print(u"  跳过（不存在）: %s" % ds)
            continue
        base = _safe_name(os.path.basename(ds))
        name = base + u'.xml'
        k = 1
        while name in used:
            k += 1
            name = u'%s_%d.xml' % (base, k)
        used[name] = True
        out_xml = os.path.join(out_dir, name)
        try:
            arcpy.XSLTransform_conversion(ds, xslt, out_xml)
            done += 1
            print(u"  %s" % out_xml)
        except Exception as e:
            print(u"  失败 %s: %s" % (ds, e))
    print(u"完成: 导出 %d/%d 个" % (done, len(ds_list)))
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
