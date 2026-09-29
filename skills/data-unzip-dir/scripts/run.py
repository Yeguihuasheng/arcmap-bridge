# -*- coding: utf-8 -*-
"""
批量解压 ZIP —— ArcMap 版

扫描文件夹（含子目录）里的全部 zip 包并批量解压到指定目录，每个包解压到以包名命名的子文件夹，用于交付包、影像分幅数据的批量落地。

参数顺序（按地理处理工具原定义）：
  1. 待扫描的文件夹
  2. 解压输出目录

用法：
    python run.py <待扫描的文件夹> <解压输出目录>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import zipfile
import arcpy







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
        print(u"用法: python run.py <待扫描的文件夹> <解压输出目录>")
        return 1
    in_folder = argv[0]
    out_folder = argv[1]
    if not os.path.isdir(in_folder):
        raise ValueError(u"输入文件夹不存在: %s" % in_folder)
    if not os.path.isdir(out_folder):
        os.makedirs(out_folder)

    zips = []
    for cur, _dirs, files in os.walk(in_folder):
        for f in files:
            if f.lower().endswith('.zip'):
                zips.append(os.path.join(cur, f))
    if not zips:
        print(u"没有找到任何 zip 文件")
        return 0

    ok = 0
    for zp in zips:
        name = os.path.splitext(os.path.basename(zp))[0]
        target = os.path.join(out_folder, name)
        if not os.path.isdir(target):
            os.makedirs(target)
        try:
            with zipfile.ZipFile(zp) as zf:
                zf.extractall(target)
            print(u"解压 %s -> %s" % (os.path.basename(zp), target))
            ok += 1
        except Exception as e:
            print(u"失败 %s: %s" % (os.path.basename(zp), e))
    print(u"完成 %d/%d 个压缩包" % (ok, len(zips)))
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
