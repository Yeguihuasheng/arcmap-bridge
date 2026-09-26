# -*- coding: utf-8 -*-
r"""打包 YghsBridge.AddIn 为 .esriaddin（ArcMap 插件包）。

包结构（照原版 arcmap-mcp 的 dist 布局，ArcMap 加载器认这个）：
    config.xml                <- 根（注意是小写 config.xml，源文件叫 Config.xml）
    Images\*.png
    Install\YghsBridge.AddIn.dll
    Install\Newtonsoft.Json.dll
    LICENSE-THIRD-PARTY.txt

用法：
    python package.py            # 用 bin\Release 下的产物打包
先跑 dotnet build -c Release。
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "bin", "Release")
PKG = os.path.join(OUT_DIR, "YghsBridge.esriaddin")

# (包内路径, 磁盘路径) —— 顺序无所谓，但清单要显式，别用 walk 扫（避免打进 pdb/obj 垃圾）
ITEMS = [
    ("config.xml", os.path.join(HERE, "Config.xml")),
    ("Install/YghsBridge.AddIn.dll", os.path.join(OUT_DIR, "YghsBridge.AddIn.dll")),
    ("Install/Newtonsoft.Json.dll", os.path.join(OUT_DIR, "Newtonsoft.Json.dll")),
    ("LICENSE-THIRD-PARTY.txt", os.path.join(HERE, "LICENSE-THIRD-PARTY.txt")),
]
for _f in sorted(os.listdir(os.path.join(HERE, "Images"))):
    ITEMS.append(("Images/" + _f, os.path.join(HERE, "Images", _f)))

missing = [d for _, d in ITEMS if not os.path.isfile(d)]
if missing:
    print("缺失文件，先 dotnet build -c Release：")
    for m in missing:
        print("   ", m)
    sys.exit(1)

# 沙箱注意：不要先删再写（os.remove 会被 shim 拦），ZipFile(path, "w") 自己会截断覆盖
with zipfile.ZipFile(PKG, "w", zipfile.ZIP_DEFLATED) as z:
    for name, disk in ITEMS:
        z.write(disk, name)

print("已打包:", PKG, os.path.getsize(PKG), "B")
with zipfile.ZipFile(PKG) as z:
    for n in z.namelist():
        print("   %-32s %d B" % (n, z.getinfo(n).file_size))
# 自检：内嵌 runner 是否带上了本次修复
dll = os.path.join(OUT_DIR, "YghsBridge.AddIn.dll")
with open(dll, "rb") as f:
    blob = f.read()
print("DLL 含 _df_de_mxd 修复标记:", blob.count(b"_df_de_mxd") > 0)
