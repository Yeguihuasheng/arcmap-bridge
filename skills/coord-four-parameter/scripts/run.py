# -*- coding: utf-8 -*-
"""
四参数坐标转换 —— ArcMap 版

用一组同名控制点（源坐标系与目标坐标系各一套 XY）按最小二乘求平面四参数（平移 DX/DY + 缩放系数 k + 旋转角 θ），并可选地把一个点/线/面要素类按该参数整体转换到目标坐标系。适用于地方独立坐标系与国家坐标系（如 CGCS2000）之间的平面转换，无需栅格投影参数、只要有控制点即可。

参数顺序（按地理处理工具原定义）：
  1. 控制点文件（UTF-8 或 GBK，每行：源X,源Y,目标X,目标Y）
  2. 要转换的要素类（留空 # 则只求参数不转换）
  3. 转换后要素类路径（apply_fc 为空时此参数忽略）
  4. 参数与残差报告输出 txt 路径

用法：
    python run.py <控制点文件（UTF-8 或 GBK，每行：源X,源Y,目标X,目标Y）> <要转换的要素类（留空 # 则只求参数不转换）> <转换后要素类路径（apply_fc 为空时此参数忽略）> <参数与残差报告输出 txt 路径>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import math
import arcpy


def _solve4(A, b):
    """高斯-约当消元解 4x4 线性方程组 A x = b。"""
    n = 4
    M = []
    for i in range(n):
        M.append(list(A[i]) + [b[i]])
    for col in range(n):
        piv = col
        for r in range(col + 1, n):
            if abs(M[r][col]) > abs(M[piv][col]):
                piv = r
        if abs(M[piv][col]) < 1e-14:
            raise ValueError(u"控制点不足或共线，正规方程奇异，无法求四参数")
        if piv != col:
            M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        for j in range(col, n + 1):
            M[col][j] = M[col][j] / pv
        for r in range(n):
            if r != col:
                f = M[r][col]
                if f != 0.0:
                    for j in range(col, n + 1):
                        M[r][j] = M[r][j] - f * M[col][j]
    return [M[i][n] for i in range(n)]


def _fit_four(ctrl):
    """ctrl: [(x0, y0, x1, y1), ...] -> [a, b, c, d]（四参数线性系数）。"""
    ATA = [[0.0] * 4 for _ in range(4)]
    ATL = [0.0] * 4
    for (x0, y0, x1, y1) in ctrl:
        rows = [
            ([1.0, x0, -y0, 0.0], x1),
            ([0.0, y0, x0, 1.0], y1),
        ]
        for row, obs in rows:
            for i in range(4):
                ATL[i] += row[i] * obs
                for j in range(4):
                    ATA[i][j] += row[i] * row[j]
    return _solve4(ATA, ATL)


def _parse_control(path):
    ctrl = []
    for line in open(path, u'rb').read().decode(u'gbk', u'replace').splitlines():
        t = line.strip()
        if not t or t.startswith(u'#'):
            continue
        parts = [p.strip() for p in t.replace(u',', u' ').split()]
        if len(parts) < 4:
            continue
        try:
            x0 = float(parts[0]); y0 = float(parts[1])
            x1 = float(parts[2]); y1 = float(parts[3])
        except ValueError:
            continue
        ctrl.append((x0, y0, x1, y1))
    if len(ctrl) < 3:
        raise ValueError(u"有效控制点少于 3 个（读到 %d 个）" % len(ctrl))
    return ctrl


def _apply_transform(shape, a, b, c, d):
    """对 arcpy 几何做四参数仿射（XY 变换，Z 保留）。"""
    def tf(x, y):
        return a + b * x - c * y, d + b * y + c * x
    gtype = shape.type
    if gtype == u'point':
        pt = shape.firstPoint
        x, y = tf(pt.X, pt.Y)
        try:
            return arcpy.Point(x, y, pt.Z)
        except Exception:
            return arcpy.Point(x, y)
    pts = []
    for part in shape:
        row = []
        for pt in part:
            if pt is None:
                row.append(None)
            else:
                x, y = tf(pt.X, pt.Y)
                try:
                    row.append(arcpy.Point(x, y, pt.Z))
                except Exception:
                    row.append(arcpy.Point(x, y))
        pts.append(row)
    if gtype == u'polyline':
        return arcpy.Polyline(arcpy.Array([arcpy.Array(p) for p in pts]))
    return arcpy.Polygon(arcpy.Array([arcpy.Array(p) for p in pts]))




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
        print(u"用法: python run.py <控制点文件（UTF-8 或 GBK，每行：源X,源Y,目标X,目标Y）> <要转换的要素类（留空 # 则只求参数不转换）> <转换后要素类路径（apply_fc 为空时此参数忽略）> <参数与残差报告输出 txt 路径>")
        return 1
    control_csv = argv[0]
    apply_fc = argv[1]
    out_fc = argv[2]
    out_report = argv[3]
    ctrl = _parse_control(control_csv)
    a, b, c, d = _fit_four(ctrl)
    k = math.sqrt(b * b + c * c)
    rot = math.degrees(math.atan2(c, b))
    dx, dy = a, d

    # 残差与中误差
    lines = [u"四参数转换结果",
             u"DX = %.6f" % dx,
             u"DY = %.6f" % dy,
             u"k  = %.10f" % k,
             u"theta = %.6f 度" % rot,
             u"（旋转角 = atan2(c,b)，弧度 %.10f）" % math.atan2(c, b),
             u"",
             u"控制点残差（dx=转换X-目标X, dy=转换Y-目标Y）："]
    sse = 0.0
    for (x0, y0, x1, y1) in ctrl:
        px = a + b * x0 - c * y0
        py = d + b * y0 + c * x0
        ex = px - x1
        ey = py - y1
        sse += ex * ex + ey * ey
        lines.append(u"  %-14.4f %-14.4f -> %-14.4f %-14.4f  dx=%+.4f dy=%+.4f"
                     % (x0, y0, x1, y1, ex, ey))
    rmse = math.sqrt(sse / (2 * len(ctrl)))
    lines.append(u"")
    lines.append(u"中误差 RMSE = %.6f（%d 个控制点）" % (rmse, len(ctrl)))

    # 写入报告
    with open(out_report, u'wb') as fh:
        fh.write(u"\n".join(lines).encode(u'utf-8-sig'))

    # 可选：转换要素类
    if apply_fc and apply_fc.strip() and apply_fc.strip() != u'#':
        if not arcpy.Exists(apply_fc):
            raise ValueError(u"要转换的要素类不存在: %s" % apply_fc)
        arcpy.env.overwriteOutput = True
        arcpy.CopyFeatures_management(apply_fc, out_fc)
        cnt = 0
        with arcpy.da.UpdateCursor(out_fc, [u'SHAPE@']) as cur:
            for (shape,) in cur:
                cur.updateRow([_apply_transform(shape, a, b, c, d)])
                cnt += 1
        lines.append(u"")
        lines.append(u"已转换要素 %d 个 -> %s" % (cnt, out_fc))
        with open(out_report, u'wb') as fh:
            fh.write(u"\n".join(lines).encode(u'utf-8-sig'))
        print(u"转换完成：%s（%d 个要素）" % (out_fc, cnt))
    else:
        print(u"仅求参数，未转换要素类")

    for ln in lines:
        print(ln)
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
