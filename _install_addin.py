# -*- coding: utf-8 -*-
r"""安装 / 覆盖升级 YghsBridge.esriaddin 到 ArcMap 10.8 AddIns 目录。

要点（照 arcmap-mcp-bridge skill）：
  - 目标 GUID 目录必须同时放「.esriaddin 包文件」+「解压后的内容」，只放包不生效。
  - 沙箱下禁止 os.remove，用 shutil.copy2 覆盖写 + zipfile.extractall 覆盖解压。

用法:
    python _install_addin.py
"""
import os
import shutil
import sys
import zipfile

GUID_DIR = r"C:\Users\Administrator\Documents\ArcGIS\AddIns\Desktop10.8\{51f4ce63-6bcf-49b2-ae3a-ba2c79ea3e1a}"
PKG = r"A:\GisProTest\.arcmapbridge\YghsBridgeArcMap\bin\Release\YghsBridge.esriaddin"
PKG_NAME = "YghsBridge.esriaddin"


def main():
    if not os.path.isfile(PKG):
        print("找不到包:", PKG)
        return 1
    if not os.path.isdir(GUID_DIR):
        print("找不到 AddIns 目录:", GUID_DIR)
        return 1

    print("包   :", PKG, os.path.getsize(PKG), "B")
    print("目标 :", GUID_DIR)

    dst_pkg = os.path.join(GUID_DIR, PKG_NAME)
    shutil.copy2(PKG, dst_pkg)          # 覆盖写，不删
    print("已覆盖包:", dst_pkg, os.path.getsize(dst_pkg), "B")

    with zipfile.ZipFile(PKG) as z:
        z.extractall(GUID_DIR)          # 逐文件覆盖写
        names = z.namelist()
    print("已解压 %d 项:" % len(names))
    for n in names:
        p = os.path.join(GUID_DIR, n.replace("/", os.sep))
        print("   %-32s %s" % (n, "OK %d B" % os.path.getsize(p) if os.path.isfile(p) else "缺失!"))

    # 校验磁盘上的 DLL 是否与包内一致
    dll_disk = os.path.join(GUID_DIR, "Install", "YghsBridge.AddIn.dll")
    with zipfile.ZipFile(PKG) as z:
        in_pkg = z.read("Install/YghsBridge.AddIn.dll")
    with open(dll_disk, "rb") as f:
        on_disk = f.read()
    same = in_pkg == on_disk
    print("\nInstall/YghsBridge.AddIn.dll 与包内一致:", same, "(%d B)" % len(on_disk))
    if not same:
        return 1

    # 目录里是否还残留旧 GUID / 旧名包
    print("\nAddIns\\Desktop10.8 下的条目:")
    root = os.path.dirname(GUID_DIR)
    for e in sorted(os.listdir(root)):
        print("   ", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
