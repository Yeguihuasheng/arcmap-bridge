# -*- coding: utf-8 -*-
"""向 ArcMap 的 Python 输入框写入一行并回车执行。
行内容从 A:\\GisProTest\\.arcmapbridge\\line.txt 读取（第一行）。
"""
import ctypes
import time
import ctypes.wintypes as w

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
ARC_MAIN = 221455584
INP = 92150794
WM_SETTEXT = 0x000C
VK_RETURN = 0x0D
EM_SETSEL = 0x00B1

with open(r"A:\GisProTest\.arcmapbridge\line.txt", "r", encoding="utf-8") as f:
    LINE = f.readline().rstrip("\r\n")
print("要执行的行:", LINE)


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
print("前置 OK")

arc_thread = user32.GetWindowThreadProcessId(w.HWND(ARC_MAIN), None)
ott = kernel32.GetCurrentThreadId()
user32.AttachThreadInput(ott, arc_thread, True)
user32.SetFocus(w.HWND(INP))

user32.SendMessageW(w.HWND(INP), WM_SETTEXT, 0, ctypes.create_unicode_buffer(LINE))
user32.SendMessageW(w.HWND(INP), EM_SETSEL, len(LINE), -1)
time.sleep(0.2)
user32.keybd_event(VK_RETURN, 0, 0, 0)
time.sleep(0.06)
user32.keybd_event(VK_RETURN, 0, 0x0002, 0)
print("已回车")
time.sleep(2.5)
user32.AttachThreadInput(ott, arc_thread, False)
