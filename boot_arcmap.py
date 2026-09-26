# -*- coding: utf-8 -*-
"""ArcMap 桥点火 v3：实时 rect 点击输入框 + AttachThreadInput 强制 SetFocus + 回车。"""
import ctypes
import ctypes.wintypes as w
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
ARC_MAIN = 221455584
INP = 92150794
LINE = 'execfile(r"A:\\GisProTest\\.arcmapbridge\\bridge_boot.py")'
VK_RETURN = 0x0D
WM_SETTEXT = 0x000C
WM_GETTEXTLENGTH = 0x000E
WM_GETTEXT = 0x000D

user32.SetWindowDisplayAffinity.argtypes = [w.HWND, w.DWORD]
user32.SetWindowDisplayAffinity.restype = w.BOOL


def get_text(h):
    n = user32.SendMessageW(w.HWND(h), WM_GETTEXTLENGTH, 0, 0)
    buf = ctypes.create_unicode_buffer(n + 2)
    user32.SendMessageW(w.HWND(h), WM_GETTEXT, n + 1, buf)
    return buf.value


def foreground():
    return user32.GetForegroundWindow()


def force_fg(hwnd, tries=8):
    for i in range(tries):
        if foreground() == hwnd:
            return True
        user32.SetForegroundWindow(w.HWND(hwnd))
        time.sleep(0.25)
        if foreground() == hwnd:
            return True
        fg = foreground()
        fgt = user32.GetWindowThreadProcessId(w.HWND(fg), None)
        ott = kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(ott, fgt, True)
        user32.BringWindowToTop(w.HWND(hwnd))
        user32.SetForegroundWindow(w.HWND(hwnd))
        user32.AttachThreadInput(ott, fgt, False)
        time.sleep(0.3)
    return foreground() == hwnd


def click(x, y):
    user32.SetCursorPos(w.INT(x), w.INT(y))
    time.sleep(0.15)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.3)


def tap_return():
    user32.keybd_event(VK_RETURN, 0, 0, 0)
    time.sleep(0.06)
    user32.keybd_event(VK_RETURN, 0, 0x0002, 0)
    time.sleep(0.5)


# 0) 前置
if not force_fg(ARC_MAIN):
    print("!! ArcMap 无法前置")
    raise SystemExit(1)
print("[0] ArcMap 前台 ✅")

# 1) 实时取输入框 rect
r = w.RECT()
user32.GetWindowRect(w.HWND(INP), ctypes.byref(r))
cx = r.left + 150
cy = (r.top + r.bottom) // 2
print("[1] 输入框 rect=(%d,%d)-(%d,%d) 点击点=(%d,%d)" % (r.left, r.top, r.right, r.bottom, cx, cy))

# 2) 点击（把焦点给输入框）
click(cx, cy)
print("[2] 已点击，前台:", foreground())

# 3) 强制 SetFocus（跨线程）
arc_thread = user32.GetWindowThreadProcessId(w.HWND(ARC_MAIN), None)
ott = kernel32.GetCurrentThreadId()
attached = user32.AttachThreadInput(ott, arc_thread, True)
sf = user32.SetFocus(w.HWND(INP))
print("[3] AttachThreadInput=%s SetFocus->%s (焦点hwnd=%s)"
      % (bool(attached), INP if sf else sf, user32.GetFocus()))

# 4) 写入启动行（保证内容正确、光标移到行尾）
user32.SendMessageW(w.HWND(INP), WM_SETTEXT, 0, ctypes.create_unicode_buffer(LINE))
time.sleep(0.2)
# EM_SETSEL 到行尾：wparam=起点, lparam=终点(-1=末尾)
user32.SendMessageW(w.HWND(INP), 0x00B1, len(LINE), -1)  # EM_SETSEL
time.sleep(0.2)
print("[4] 内容:", repr(get_text(INP)[:60]), "…（已选中到行尾）")

# 5) 回车（真键盘）
tap_return()
print("[5] 已回车")
time.sleep(3.0)

inp_now = get_text(INP)
print("[6] 输入框现在:", repr(inp_now[:60]), "| 长度:", len(inp_now))
print("    心跳文件检查看下面。")
user32.AttachThreadInput(ott, arc_thread, False)
