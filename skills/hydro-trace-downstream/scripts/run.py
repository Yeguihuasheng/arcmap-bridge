# -*- coding: utf-8 -*-
"""
按流向栅格追踪下游路径 —— ArcMap 版

从一批起点出发沿 D8 流向栅格逐像元追踪水流路径，一直追到洼地（汇）或栅格边界，输出带起点编号、步数、路径长度的追踪线；可选配 DEM 给每个折点赋高程，得到三维水流路径。常用于校核河网提取结果、判断某个点最终汇入何处。

参数顺序（按地理处理工具原定义）：
  1. 输入起点要素（点）
  2. 输入流向栅格（D8 编码 1/2/4/8/16/32/64/128）
  3. 输出追踪线要素类
  4. 表面栅格 DEM（可选，给折点赋 Z；不需要填 #）

用法：
    python run.py <输入起点要素（点）> <输入流向栅格（D8 编码 1/2/4/8/16/32/64/128）> <输出追踪线要素类> <表面栅格 DEM（可选，给折点赋 Z；不需要填 #）>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import arcpy


_D8 = {1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1),
       16: (0, -1), 32: (-1, -1), 64: (-1, 0), 128: (-1, 1)}


def d8_step(value):
    """D8 流向编码 -> (行增量, 列增量)；非 8 个合法值视为洼地，原地不动。"""
    return _D8.get(int(value), (0, 0))




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
        print(u"用法: python run.py <输入起点要素（点）> <输入流向栅格（D8 编码 1/2/4/8/16/32/64/128）> <输出追踪线要素类> <表面栅格 DEM（可选，给折点赋 Z；不需要填 #）>")
        return 1
    in_features = argv[0]
    fdr = argv[1]
    out_fc = argv[2]
    surface = argv[3]
    arcpy.env.overwriteOutput = True
    n0 = int(arcpy.GetCount_management(in_features).getOutput(0))
    if n0 == 0:
        raise RuntimeError(u"起点要素里没有要素，无法追踪")

    ras = arcpy.Raster(fdr)
    cw = float(ras.meanCellWidth)
    ch = float(ras.meanCellHeight)
    nrow = int(ras.height)
    ncol = int(ras.width)
    x0 = float(ras.extent.XMin)
    y1 = float(ras.extent.YMax)
    sr = arcpy.Describe(fdr).spatialReference

    fdr_arr = arcpy.RasterToNumPyArray(fdr, nodata_to_value=0)
    dem_arr = None
    if surface and surface.strip() and surface.strip() != u'#':
        dem_arr = arcpy.RasterToNumPyArray(surface, nodata_to_value=0)
    has_z = dem_arr is not None

    out_dir, out_name = os.path.split(out_fc)
    if not out_dir:
        out_dir = arcpy.env.workspace
    arcpy.CreateFeatureclass_management(out_dir, out_name, "POLYLINE", "",
                                        "ENABLED" if has_z else "DISABLED",
                                        "DISABLED", sr)
    arcpy.AddField_management(out_fc, "ORIG_OID", "LONG")
    arcpy.AddField_management(out_fc, "STEP_CNT", "LONG")
    arcpy.AddField_management(out_fc, "LEN_M", "DOUBLE")
    arcpy.AddField_management(out_fc, "END_TYPE", "TEXT", "", "", 20)

    def _z(r, c):
        if dem_arr is None:
            return 0.0
        try:
            return float(dem_arr[r, c])
        except Exception:
            return 0.0

    def _xy(r, c):
        """像元行列号 -> 像元中心的地图坐标（0 起始，与 numpy 索引一致）"""
        return (x0 + (c + 0.5) * cw, y1 - (r + 0.5) * ch)

    def _idx(x, y):
        r = int((y1 - y) / ch)
        c = int((x - x0) / cw)
        if r < 0:
            r = 0
        if c < 0:
            c = 0
        if r > nrow - 1:
            r = nrow - 1
        if c > ncol - 1:
            c = ncol - 1
        return (r, c)

    max_step = nrow * ncol
    rows = []
    with arcpy.da.SearchCursor(in_features, ["SHAPE@XY", "OID@"]) as cur:
        for xy, oid in cur:
            if xy is None:
                continue
            px, py = float(xy[0]), float(xy[1])
            r, c = _idx(px, py)
            pts = arcpy.Array()
            pts.add(arcpy.Point(px, py, _z(r, c)))
            step = 0
            total = 0.0
            end_type = u"maxstep"
            while step < max_step:
                dr, dc = d8_step(fdr_arr[r, c])
                if dr == 0 and dc == 0:
                    end_type = u"sink"
                    break
                nr, nc = r + dr, c + dc
                if nr < 0 or nr >= nrow or nc < 0 or nc >= ncol:
                    end_type = u"boundary"
                    break
                nx, ny = _xy(nr, nc)
                last = pts.getObject(pts.count - 1)
                dx = nx - last.X
                dy = ny - last.Y
                dz = _z(nr, nc) - last.Z
                total += (dx * dx + dy * dy + dz * dz) ** 0.5
                pts.add(arcpy.Point(nx, ny, _z(nr, nc)))
                r, c = nr, nc
                step += 1
            if pts.count >= 2:
                rows.append((arcpy.Polyline(pts, sr, has_z, False),
                             oid, step, total, end_type))

    if rows:
        with arcpy.da.InsertCursor(out_fc, ["SHAPE@", "ORIG_OID", "STEP_CNT",
                                            "LEN_M", "END_TYPE"]) as ic:
            for row in rows:
                ic.insertRow(row)
    print(u"追踪线 %d 条（起点 %d 个）-> %s" % (len(rows), n0, out_fc))
    if has_z:
        print(u"已按 DEM 给折点赋高程，输出为带 Z 的 POLYLINE")
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
