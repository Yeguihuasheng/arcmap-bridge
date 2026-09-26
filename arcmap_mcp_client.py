# -*- coding: utf-8 -*-
"""arcmap-mcp 桥的直连客户端（不走它的 MCP 服务器，直接说 socket 协议）。

协议：127.0.0.1:27179，一次连接发一条 JSON {"type":..., "params":{...}}，
读直到对端关闭，响应为 JSON。

用法:
    python arcmap_mcp_client.py ping
    python arcmap_mcp_client.py get_arcmap_info
    python arcmap_mcp_client.py list_layers
    python arcmap_mcp_client.py exec --code-file 脚本.py     # 在 ArcMap 的 py2.7 里执行
    python arcmap_mcp_client.py exec -c "import arcpy; print(arcpy.GetInstallInfo()['Version'])"
"""
import json
import socket
import sys

HOST = "127.0.0.1"
PORT = 27179


def send(ctype, params=None, timeout=120.0):
    msg = json.dumps({"type": ctype, "params": params or {}}).encode("utf-8")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        try:
            s.connect((HOST, PORT))
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            return {"ok": False, "estado": "puente_caido",
                    "error": "无法连接桥接服务 %s:%s（ArcMap 未启动或插件未开启）：%s" % (HOST, PORT, e)}
        s.sendall(msg)
        buf = b""
        while True:
            try:
                chunk = s.recv(65536)
            except socket.timeout:
                return {"ok": False, "estado": "puente_ocupado",
                        "error": "桥接服务存活但 %s 秒内无响应（ArcMap 可能正忙，如运行耗时的地理处理）" % timeout}
            if not chunk:
                break
            buf += chunk
        if not buf:
            return {"ok": False, "error": "连接被关闭且无响应"}
        try:
            return json.loads(buf.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {"ok": False, "error": "响应不可读（%d 字节）：%s" % (len(buf), buf[:200])}
    finally:
        s.close()


def show(r):
    if isinstance(r, dict):
        for k in sorted(r):
            v = r[k]
            s = json.dumps(v, ensure_ascii=False) if not isinstance(v, (str, int, float, bool)) else str(v)
            if len(s) > 600:
                s = s[:600] + " …(截断)"
            print("  %-14s %s" % (k + ":", s))
    else:
        print(r)


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]

    if cmd == "ping":
        show(send("ping", {}))
        return 0

    if cmd == "info":
        show(send("get_arcmap_info", {}))
        return 0

    if cmd == "layers":
        show(send("list_layers", {}))
        return 0

    if cmd == "exec":
        code = None
        if "--code-file" in argv:
            i = argv.index("--code-file")
            if i + 1 >= len(argv):
                print("用法: exec --code-file <py2脚本>")
                return 2
            with open(argv[i + 1], "r", encoding="utf-8") as f:
                code = f.read()
        elif "-c" in argv:
            i = argv.index("-c")
            code = " ".join(argv[i + 1:])
            if not code.strip():
                print("用法: exec -c \"<py2代码>\"")
                return 2
        if code is None or not code.strip():
            print("用法: exec --code-file <py2脚本>  或  exec -c \"<py2代码>\"")
            return 2
        # py2.7 陷阱：exec(unicode串) 遇到 coding 声明会报
        # "encoding declaration in Unicode string" → 一律剥掉声明行（源文件已是 utf-8 读取）
        lines = code.splitlines()
        if lines and lines[0].startswith("#") and "coding" in lines[0]:
            lines = lines[1:]
        # py2.7 陷阱：from __future__ 必须在文件头 → 从用户代码抽出，合并进垫片
        futures = [l for l in lines if l.startswith("from __future__")]
        lines = [l for l in lines if not l.startswith("from __future__")]
        code = "\n".join(lines)
        # py2.7 陷阱：runner 的 stdout 是字节 StringIO，打印 unicode 会 UnicodeDecodeError
        # → 垫一层把 unicode 编成 utf-8 再写
        SHIM = "\n".join(futures + [
            "import sys as _s",
            "class _U8W(object):",
            "    def __init__(self, o): self._o = o",
            "    def write(self, s):",
            "        if isinstance(s, unicode): s = s.encode('utf-8')",
            "        return self._o.write(s)",
            "    def flush(self):",
            "        try: self._o.flush()",
            "        except Exception: pass",
            "_s.stdout = _U8W(_s.stdout)",
        ]) + "\n"
        code = SHIM + code
        code += "\n"
        r = send("execute_code", {"code": code, "usar_documento": False}, timeout=900.0)
        show(r)
        return 0 if r.get("ok") else 1

    print("未知命令:", cmd)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
