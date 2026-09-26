# -*- coding: utf-8 -*-
"""ArcMap 10.8（Python 2.7）桥 v1.0 —— 在 ArcMap 的 Python 窗口驻留后台线程。

启动（在 ArcMap 的 Python 窗口里执行一次，之后本会话内一直有效）：
    execfile(r"A:\\GisProTest\\.arcmapbridge\\bridge_boot.py")

协议（与 Pro 的文件桥一致）：
    in\\<rid>.py  -> 在本进程内 exec -> out\\<rid>.txt（=== OK === / === ERROR ===，以 ===EOF=== 结尾）
    处理完归档到 done\\ ；写入 in\\STOP 停止线程。

注意：
  * ArcMap 的 Python 是 2.7 —— 丢进来的脚本必须按 2.7 语法写（或用 2/3 兼容写法）。
  * 桥线程是后台线程：arcpy 可用；arcpy.mapping / CURRENT 这类要主线程的活别放这（那得在 Python 窗口里手敲）。
  * 不自动保活：防止把 ArcMap 界面冻死（与 Pro 桥同样的教训）。
"""
from __future__ import print_function

import os
import sys
import time
import threading
import traceback

BRIDGE_DIR = r"A:\GisProTest\.arcmapbridge"
IN_DIR = os.path.join(BRIDGE_DIR, "in")
OUT_DIR = os.path.join(BRIDGE_DIR, "out")
DONE_DIR = os.path.join(BRIDGE_DIR, "done")
HB_FILE = os.path.join(BRIDGE_DIR, "heartbeat.txt")
LOG_FILE = os.path.join(BRIDGE_DIR, "bridge.log")
EOF_SENTINEL = "===EOF==="
POLL = 0.4
RID_PREFIX = "_tmp_"

_state = {"thread": None, "stop": False}


def log(msg):
    try:
        with open(LOG_FILE, "ab") as f:
            f.write((time.strftime("%Y-%m-%d %H:%M:%S") + " [pid " + str(os.getpid())
                     + "] " + msg + "\n").encode("utf-8"))
    except Exception:
        pass


def ensure_dirs():
    for d in (IN_DIR, OUT_DIR, DONE_DIR):
        if not os.path.isdir(d):
            os.makedirs(d)


class _Buf(object):
    """py2 安全的 stdout 缓冲：bytes / unicode 都吞。"""

    def __init__(self):
        self.parts = []

    def write(self, s):
        try:
            if isinstance(s, str):
                s = s.decode("utf-8", "replace")
            elif not isinstance(s, unicode):
                s = unicode(s)
        except Exception:
            s = repr(s)
        self.parts.append(s)

    def flush(self):
        pass

    def getvalue(self):
        return "".join(self.parts)


def _exec_capture(path):
    """在 py2 里执行脚本并捕获 stdout/异常。返回 (ok, text)。"""
    buf = _Buf()
    old = sys.stdout
    ok = True
    try:
        with open(path, "rb") as f:
            raw = f.read()
        if raw.startswith("\xef\xbb\xbf"):
            raw = raw[3:]
        src = raw.decode("utf-8")
        try:
            # 首选：编译 unicode 串（不要求 coding 声明，中文直接可用）
            code = compile(src, path, "exec")
        except SyntaxError as e:
            if "encoding declaration" not in str(e):
                raise
            # 源码里带 coding 声明时，unicode 编译会报
            # "encoding declaration in Unicode string" —— 改按字节编译
            code = compile(src.encode("utf-8"), path, "exec")
        g = {"__name__": "__main__", "__file__": path}
        sys.stdout = buf
        try:
            exec(code, g)
            try:
                result = g.get("__result__")
                if result is not None:
                    buf.write("\n__result__ = " + repr(result) + "\n")
            except Exception:
                pass
        except SystemExit as e:
            sys.stdout = old
            code0 = 1
            try:
                code0 = int(e.code)
            except Exception:
                try:
                    code0 = 0 if e.code in (None, True) else 1
                except Exception:
                    code0 = 1
            ok = (code0 == 0)
            if not ok:
                buf.write("SystemExit(%s)\n" % (e.code,))
        except BaseException:
            sys.stdout = old
            ok = False
            buf.write(traceback.format_exc())
        finally:
            sys.stdout = old
    except Exception:
        sys.stdout = old
        ok = False
        buf.write("桥内错误（读文件/编译失败）:\n" + traceback.format_exc())
    text = buf.getvalue()
    return ok, (text if text else "(无输出)\n")


def _list_jobs():
    jobs = []
    try:
        for name in os.listdir(IN_DIR):
            if name.endswith(".py") and not name.startswith(RID_PREFIX):
                jobs.append(os.path.join(IN_DIR, name))
    except Exception:
        pass
    jobs.sort()
    return jobs


def _archive(src, rid, ok):
    try:
        with open(src, "rb") as f:
            data = f.read()
        dst = os.path.join(DONE_DIR, ("OK_" if ok else "ERR_") + rid + ".py")
        with open(dst, "wb") as f:
            f.write(data)
        os.remove(src)
    except Exception as e:
        log("archive failed: " + str(e))


def _loop():
    log("loop start")
    ensure_dirs()
    while not _state["stop"]:
        try:
            with open(HB_FILE, "wb") as f:
                f.write(("RUNNING pid=" + str(os.getpid()) + " "
                         + time.strftime("%Y-%m-%d %H:%M:%S")).encode("utf-8"))
        except Exception:
            pass
        if os.path.exists(os.path.join(IN_DIR, "STOP")):
            log("STOP received")
            _state["stop"] = True
            try:
                os.remove(os.path.join(IN_DIR, "STOP"))
            except Exception:
                pass
            break
        for path in _list_jobs():
            rid = os.path.splitext(os.path.basename(path))[0]
            ok, text = _exec_capture(path)
            head = "=== OK ===\n" if ok else "=== ERROR ===\n"
            with open(os.path.join(OUT_DIR, rid + ".txt"), "wb") as f:
                f.write((head + text + "\n" + EOF_SENTINEL + "\n").encode("utf-8"))
            _archive(path, rid, ok)
            log("job " + rid + " ok=" + str(ok))
        time.sleep(POLL)
    log("loop end")


def start_bridge():
    ensure_dirs()
    if _state["thread"] is not None and _state["thread"].isAlive():
        print("[arcmap-bridge] 已在运行（v1.0），无需重复启动")
        return
    _state["stop"] = False
    t = threading.Thread(target=_loop)
    t.setDaemon(True)
    t.start()
    _state["thread"] = t
    print("[arcmap-bridge] 后台通道已启动 v1.0（ArcMap / Python " + sys.version.split()[0] + "）")
    print("    目录:", BRIDGE_DIR)
    print("    外部投递: python A:\\GisProTest\\.arcmapbridge\\send_arcmap.py -c \"print(1+1)\"")


def stop_bridge():
    _state["stop"] = True
    print("[arcmap-bridge] 已请求停止")


# ---- execfile 进来就直接启动（幂等） ----
ensure_dirs()
start_bridge()

if os.environ.get("ARCMAP_BRIDGE_STANDALONE") == "1":
    print("[arcmap-bridge] 独立调试模式，保活中…（Ctrl+C 退出）")
    try:
        while _state["thread"] is not None and _state["thread"].isAlive():
            time.sleep(1)
    except KeyboardInterrupt:
        _state["stop"] = True
