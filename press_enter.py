# -*- coding: utf-8 -*-
"""给 ArcMap 的 Python 输入框补一个真回车（把已粘贴的行执行掉）。"""
import ctypes
import ctypes.wintypes as w
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
ARC_MAIN = 221455584
INP = 92150794
VK_RETURN = 0x0D


def force_fg(hwnd, tries=8):
    for i in range(tries):
        if user32.GetForegroundWindow() == hwnd:
            return True
        user32.SetForegroundWindow(w.HWND(hwnd))
        time.sleep(0.25)
        if user32.GetForegroundWindow() == hwnd:
            return True
        fg = user32.GetForegroundWindow()
        fgt = user32.GetWindowThreadProcessId(w.HWND(fg), None)
        ott = kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(ott, fgt, True)
        user32.BringWindowToTop(w.HWND(hwnd))
        user32.SetForegroundWindow(w.HWND(hwnd))
        user32.AttachThreadInput(ott, fgt, False)
        time.sleep(0.3)
    return user32.GetForegroundWindow() == hwnd


if not force_fg(ARC_MAIN):
    print("!! ArcMap 无法前置")
    raise SystemExit(1)
print("ArcMap 前台 ✅")

arc_thread = user32.GetWindowThreadProcessId(w.HWND(ARC_MAIN), None)
ott = kernel32.GetCurrentThreadId()
user32.AttachThreadInput(ott, arc_thread, True)
user32.SetFocus(w.HWND(INP))
time.sleep(0.2)
print("焦点已设到输入框")

# 连按两次回车：第一次执行/退出多行模式，第二次兜底
user32.keybd_event(VK_RETURN, 0, 0, 0)
time.sleep(0.08)
user32.keybd_event(VK_RETURN, 0, 0x0002, 0)
time.sleep(2.0)
user32.keybd_event(VK_RETURN, 0, 0, 0)
time.sleep(0.08)
user32.keybd_event(VK_RETURN, 0, 0x0002, 0)
print("已补两次回车")
time.sleep(3.0)
user32.AttachThreadInput(ott, arc_thread, False)
