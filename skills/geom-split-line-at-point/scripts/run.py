# -*- coding: utf-8 -*-
"""
用点打断线 —— ArcMap 版

把落在（或贴近）线上的点作为断点，把线在断点处切分成多段，属性保留到每一段。用于把道路在交叉口/门牌点处打断、管线在桩号点处断开、河流在监测断面处切开。

参数顺序（按地理处理工具原定义）：
  1. 输入线要素
  2. 断点要素
  3. 输出打断后的线要素
  4. 点吸附容差（点离线小于该值视为在线上；填 # 表示必须严格落在线上）

用法：
    python run.py <输入线要素> <断点要素> <输出打断后的线要素> <点吸附容差（点离线小于该值视为在线上；填 # 表示必须严格落在线上）>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import math
import arcpy


def _u(v):
    if v is None:
        return u''
    if isinstance(v, bytes):
        for enc in (u'mbcs', u'utf-8', u'gbk', u'latin-1'):
            try:
                return v.decode(enc)
            except Exception:
                continue
        return v.decode(u'utf-8', u'replace')
    return u'%s' % v


def _split(text):
    t = (text or u'').strip()
    if not t or t == u'#':
        return []
    return [p.strip() for p in t.split(u';') if p.strip()]


def _has_field(ds, name):
    for f in arcpy.ListFields(ds):
        if f.name.upper() == name.upper():
            return True
    return False

def _attr_fields(fc):
    """非 OID/Geometry/Shape 系统字段名列表（保持原顺序）。"""
    return [f.name for f in arcpy.ListFields(fc)
            if f.type not in (u'OID', u'Geometry')
            and f.name.lower() not in (u'shape_length', u'shape_area')]

def _cut_piece(piece, pt_geom, sr, tol):
    """在 pt 处把 piece 切成两段；返回 [a, b] 或 None（切不动/在端点）。"""
    try:
        if pt_geom.distanceTo(piece) > tol:
            return None
        m0 = piece.measureOnLine(pt_geom, False)
    except Exception:
        return None
    L = piece.length
    if L <= 0:
        return None
    eps = max(L * 1e-6, 1e-9)
    if m0 <= eps or m0 >= L - eps:
        return None
    a = piece.positionAlongLine(max(0.0, m0 - eps), False)
    b = piece.positionAlongLine(min(L, m0 + eps), False)
    p = pt_geom.firstPoint
    dx = b.firstPoint.X - a.firstPoint.X
    dy = b.firstPoint.Y - a.firstPoint.Y
    n = (dx * dx + dy * dy) ** 0.5
    if n < 1e-12:
        dx, dy, n = 1.0, 0.0, 1.0
    d = max(L * 0.01, 1.0)
    for k in (0, 1, -1):
        ang = k * 0.7853981633974483  # 0 / +45° / -45°
        c = math.cos(ang)
        s = math.sin(ang)
        ux = (dx * c - dy * s) / n
        uy = (dx * s + dy * c) / n
        seg = arcpy.Polyline(arcpy.Array([
            arcpy.Point(p.X - ux * d, p.Y - uy * d),
            arcpy.Point(p.X + ux * d, p.Y + uy * d)]), sr)
        try:
            res = piece.cut(seg)
        except Exception:
            res = None
        if res and len(res) == 2:
            return res
    return None




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
    if len(argv) < 4:
        print(u"用法: python run.py <输入线要素> <断点要素> <输出打断后的线要素> <点吸附容差（点离线小于该值视为在线上；填 # 表示必须严格落在线上）>")
        return 1
    in_line_fc = argv[0]
    in_pt_fc = argv[1]
    out_line_fc = argv[2]
    search_tol = argv[3]
    arcpy.env.overwriteOutput = True
    tol_s = (search_tol or u'').strip()
    tol = 0.0
    if tol_s and tol_s != u'#':
        tol = tol_s
    sr = arcpy.Describe(in_line_fc).spatialReference

    pts = []
    with arcpy.da.SearchCursor(in_pt_fc, ["SHAPE@"]) as cur:
        for (g,) in cur:
            if g is not None:
                pts.append(g)
    if not pts:
        raise RuntimeError(u"断点要素里没有要素")

    out_dir, out_name = os.path.split(out_line_fc)
    if not out_dir:
        out_dir = arcpy.env.workspace
    arcpy.CreateFeatureclass_management(out_dir, out_name, "POLYLINE",
                                        in_line_fc, "", "", sr)
    in_fields = _attr_fields(in_line_fc)
    out_fields = _attr_fields(out_line_fc)

    n_lines = int(arcpy.GetCount_management(in_line_fc).getOutput(0))
    total_out = 0
    cut_cnt = 0
    with arcpy.da.InsertCursor(out_line_fc, ["SHAPE@"] + out_fields) as ic:
        with arcpy.da.SearchCursor(in_line_fc, ["SHAPE@"] + in_fields) as sc:
            for row in sc:
                geom = row[0]
                attrs = row[1:]
                if geom is None:
                    continue
                pieces = [geom]
                for p in pts:
                    newp = []
                    did = False
                    for piece in pieces:
                        if not did:
                            res = _cut_piece(piece, p, sr, tol)
                            if res:
                                newp.extend(res)
                                did = True
                                continue
                        newp.append(piece)
                    if did:
                        cut_cnt += 1
                    pieces = newp
                for piece in pieces:
                    ic.insertRow([piece] + list(attrs))
                    total_out += 1
    print(u"打断 -> %s（%d 条线 -> %d 段，有效断点 %d 个）"
          % (out_line_fc, n_lines, total_out, cut_cnt))
    if total_out == n_lines:
        print(u"提示: 段数没增加，说明没有断点真正落在线上（检查容差）")
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
