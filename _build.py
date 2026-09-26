# -*- coding: utf-8 -*-
r"""编译 YghsBridge.AddIn.csproj（Release）。用 Python 起进程，避免 shell 误判。"""
import os
import subprocess
import sys

PROJ = r"A:\GisProTest\.arcmapbridge\YghsBridgeArcMap\YghsBridge.AddIn.csproj"
CWD = os.path.dirname(PROJ)


def main():
    r = subprocess.run(["dotnet", "build", PROJ, "-c", "Release", "-v:m", "-nologo"],
                       cwd=CWD, capture_output=True)
    out = (r.stdout or b"").decode("utf-8", "replace")
    err = (r.stderr or b"").decode("utf-8", "replace")
    print(out)
    if err.strip():
        print("--- stderr ---")
        print(err)
    print("exit code:", r.returncode)
    dll = os.path.join(CWD, "bin", "Release", "YghsBridge.AddIn.dll")
    if os.path.isfile(dll):
        import time
        print("DLL:", dll, os.path.getsize(dll), "B",
              time.strftime("%m-%d %H:%M:%S", time.localtime(os.path.getmtime(dll))))
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
