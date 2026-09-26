# -*- coding: utf-8 -*-
"""ArcMap 10.8 桥的外部客户端（Python 3，在普通终端跑）。

用法:
    python send_arcmap.py status                    # 桥是否在线（看心跳）
    python send_arcmap.py -c "print(1+1)"           # 在 ArcMap 内执行代码（**Python 2.7 语法**）
    python send_arcmap.py 脚本.py                   # 在 ArcMap 内执行脚本文件
    python send_arcmap.py 脚本.py --timeout 600
    python send_arcmap.py stop                      # 停止桥线程（写 in\\STOP）

注意:
  * ArcMap 的 Python 是 **2.7** —— -c 与脚本文件都要用 2.7 兼容语法（不能有 f-string、print 函数特性等）。
  * 桥线程跑在 ArcMap 进程内：arcpy 可用（Desktop 许可），但 arcpy.mapping/CURRENT 这类主线程的活不行。
"""
import os
import sys
import time
import uuid

BRIDGE_DIR = r"A:\GisProTest\.arcmapbridge"
IN_DIR = os.path.join(BRIDGE_DIR, "in")
OUT_DIR = os.path.join(BRIDGE_DIR, "out")
HB_FILE = os.path.join(BRIDGE_DIR, "heartbeat.txt")
EOF_SENTINEL = "===EOF==="
POLL = 0.3


def hb_age():
    if not os.path.exists(HB_FILE):
        return None
    try:
        return time.time() - os.path.getmtime(HB_FILE)
    except Exception:
        return None


def dispatch(code, timeout, label):
    os.makedirs(IN_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    rid = time.strftime("%H%M%S") + "-" + uuid.uuid4().hex[:6]
    tmp = os.path.join(IN_DIR, "_tmp_" + rid)
    dst = os.path.join(IN_DIR, rid + ".py")
    out = os.path.join(OUT_DIR, rid + ".txt")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        os.replace(tmp, dst)
    except Exception:
        with open(dst, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            os.remove(tmp)
        except Exception:
            pass

    print("投递到 ArcMap 内执行：%s（%d 字节，rid=%s）" % (label, len(code), rid))
    t0 = time.time()
    waited = 0.0
    while waited < timeout:
        if os.path.exists(out):
            break
        time.sleep(POLL)
        waited += POLL
    if not os.path.exists(out):
        print("超时 %.0f 秒无响应。" % timeout)
        print("  可能：桥没启动（在 ArcMap 的 Python 窗口执行 execfile 那行）、脚本把桥线程卡死、或 ArcMap 正忙。")
        return 4
    with open(out, "r", encoding="utf-8", errors="replace") as f:
        txt = f.read()
    ok = txt.startswith("=== OK ===")
    body = txt.replace("=== OK ===", "").replace("=== ERROR ===", "")
    print(body.replace(EOF_SENTINEL, "").rstrip())
    print("--- %s，用时 %.1fs ---" % ("成功" if ok else "出错", time.time() - t0))
    # 不删 out 文件（沙箱会拦截并刷 stderr；out 文件留着无妨，可当历史记录）
    return 0 if ok else 1


def status():
    age = hb_age()
    if age is None:
        print("桥状态：未启动（没有心跳文件）")
        return 1
    on = age < 10
    print("桥状态：%s（心跳 %.0f 秒前）" % ("在线 ✅" if on else "心跳陈旧 %.0f 秒 ❌" % age, age))
    return 0 if on else 1


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    timeout = 600.0
    if "--timeout" in argv:
        i = argv.index("--timeout")
        timeout = float(argv[i + 1])
        del argv[i : i + 2]
    cmd = argv[0]

    if cmd == "status":
        return status()

    if cmd == "stop":
        os.makedirs(IN_DIR, exist_ok=True)
        with open(os.path.join(IN_DIR, "STOP"), "w") as f:
            f.write("stop")
        print("已写入 STOP，桥线程将在下一个轮询周期退出。")
        return 0

    if cmd == "-c":
        code = " ".join(argv[1:])
        if not code:
            print("用法: send_arcmap.py -c \"<Python 2.7 代码>\"")
            return 2
        if not code.startswith("#"):
            code = "# -*- coding: utf-8 -*-\n" + code
        return dispatch(code, timeout, "内联代码")

    if os.path.exists(cmd):
        with open(cmd, "r", encoding="utf-8") as f:
            code = f.read()
        return dispatch(code, timeout, os.path.basename(cmd))

    print("未知子命令:", cmd)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
