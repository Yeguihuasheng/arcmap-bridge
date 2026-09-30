# -*- coding: utf-8 -*-
"""
按坡度限制在 DEM 上找最短路径 —— ArcMap 版

在 DEM 上以「三维实际距离」为代价做 Dijkstra 最短路搜索，相邻像元之间的坡度超过阈值就视为不可通行，输出起点到终点的路径线（可带 Z）。用于选线、巡线、施工便道、管线走向这类"绕开陡坡找最短"的场景。

参数顺序（按地理处理工具原定义）：
  1. 输入高程栅格 DEM
  2. 起点 X 坐标（与 DEM 同坐标系）
  3. 起点 Y 坐标
  4. 终点 X 坐标
  5. 终点 Y 坐标
  6. 最大允许坡度（高差/水平距离，如 0.3 表示 30%）
  7. 输出路径线要素类

用法：
    python run.py <输入高程栅格 DEM> <起点 X 坐标（与 DEM 同坐标系）> <起点 Y 坐标> <终点 X 坐标> <终点 Y 坐标> <最大允许坡度（高差/水平距离，如 0.3 表示 30%）> <输出路径线要素类>
"""
from __future__ import print_function, unicode_literals
import os
import sys
import math
import heapq
import arcpy


def _idx_of(x, y, x0, y1, cw, ch, nrow, ncol):
    c = int((x - x0) / cw)
    r = int((y1 - y) / ch)
    return (r, c)


def _xy_of(r, c, x0, y1, cw, ch):
    return (x0 + (c + 0.5) * cw, y1 - (r + 0.5) * ch)


def shortest_path(arr, nodata, cw, ch, sr_idx, sc_idx, er_idx, ec_idx, max_slope):
    """Dijkstra 最短路。返回 [(行, 列), ...] 或 None（不可达）。"""
    nrow, ncol = arr.shape[0], arr.shape[1]
    inf = float('inf')
    dist = {}
    prev = {}
    dist[(sr_idx, sc_idx)] = 0.0
    heap = [(0.0, sr_idx, sc_idx)]
    target = (er_idx, ec_idx)
    visited = set()
    nb = [(-1, 0, cw), (1, 0, cw), (0, -1, cw), (0, 1, cw),
          (-1, -1, cw * math.sqrt(2.0)), (-1, 1, cw * math.sqrt(2.0)),
          (1, -1, cw * math.sqrt(2.0)), (1, 1, cw * math.sqrt(2.0))]

    while heap:
        d, r, c = heapq.heappop(heap)
        if (r, c) in visited:
            continue
        visited.add((r, c))
        if (r, c) == target:
            break
        z0 = float(arr[r, c])
        for dr, dc, step in nb:
            nr, nc = r + dr, c + dc
            if nr < 0 or nr >= nrow or nc < 0 or nc >= ncol:
                continue
            z1 = float(arr[nr, nc])
            if z1 == nodata or z0 == nodata:
                continue
            dz = z1 - z0
            if abs(dz) / step > max_slope:
                continue
            nd = d + math.sqrt(step * step + dz * dz)
            if nd < dist.get((nr, nc), inf):
                dist[(nr, nc)] = nd
                prev[(nr, nc)] = (r, c)
                heapq.heappush(heap, (nd, nr, nc))

    if target not in dist:
        return None
    path = [target]
    cur = target
    while cur != (sr_idx, sc_idx):
        cur = prev[cur]
        path.append(cur)
    path.reverse()
    return path




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
    if len(argv) < 7:
        print(u"用法: python run.py <输入高程栅格 DEM> <起点 X 坐标（与 DEM 同坐标系）> <起点 Y 坐标> <终点 X 坐标> <终点 Y 坐标> <最大允许坡度（高差/水平距离，如 0.3 表示 30%）> <输出路径线要素类>")
        return 1
    dem = argv[0]
    start_x = float(argv[1])
    start_y = float(argv[2])
    end_x = float(argv[3])
    end_y = float(argv[4])
    max_slope = float(argv[5])
    out_fc = argv[6]
    arcpy.env.overwriteOutput = True
    ras = arcpy.Raster(dem)
    cw = float(ras.meanCellWidth)
    ch = float(ras.meanCellHeight)
    nrow = int(ras.height)
    ncol = int(ras.width)
    x0 = float(ras.extent.XMin)
    y1 = float(ras.extent.YMax)
    if nrow * ncol > 500000:
        print(u"警告: DEM 有 %d x %d = %d 个像元，可能非常慢，建议先裁出走廊带"
              % (nrow, ncol, nrow * ncol))

    sr_desc = arcpy.Describe(dem)
    try:
        if sr_desc.spatialReference.type.lower() == 'geographic':
            raise RuntimeError(u"DEM 是地理坐标系，请先用投影坐标系的 DEM")
    except RuntimeError:
        raise
    except Exception:
        pass

    arr = arcpy.RasterToNumPyArray(dem)
    try:
        nodata = float(ras.noDataValue)
    except Exception:
        nodata = float(arr.min())

    sr_i, sc_i = _idx_of(start_x, start_y, x0, y1, cw, ch, nrow, ncol)
    er_i, ec_i = _idx_of(end_x, end_y, x0, y1, cw, ch, nrow, ncol)
    for nm, r, c in ((u"起点", sr_i, sc_i), (u"终点", er_i, ec_i)):
        if r < 0 or r >= nrow or c < 0 or c >= ncol:
            raise RuntimeError(u"%s落在 DEM 范围外（行列 %d,%d）" % (nm, r, c))
        if float(arr[r, c]) == nodata:
            raise RuntimeError(u"%s落在 DEM 的 NoData 上" % nm)

    print(u"DEM %d x %d，像元 %.4g m；起点(%d,%d) 终点(%d,%d)"
          % (nrow, ncol, cw, sr_i, sc_i, er_i, ec_i))
    path = shortest_path(arr, nodata, cw, ch, sr_i, sc_i, er_i, ec_i, max_slope)
    if not path:
        raise RuntimeError(u"在坡度阈值 %.4g 下起点到终点不可达，请放宽 max_slope 或换个终点"
                           % max_slope)

    pts = arcpy.Array()
    for r, c in path:
        x, y = _xy_of(r, c, x0, y1, cw, ch)
        pts.add(arcpy.Point(x, y, float(arr[r, c])))
    # 首尾用用户给的真实坐标，避免像元中心带来的半格偏差
    pts.getObject(0).X = start_x
    pts.getObject(0).Y = start_y
    pts.getObject(pts.count - 1).X = end_x
    pts.getObject(pts.count - 1).Y = end_y

    out_dir, out_name = os.path.split(out_fc)
    if not out_dir:
        out_dir = arcpy.env.workspace
    sr = arcpy.Describe(dem).spatialReference
    arcpy.CreateFeatureclass_management(out_dir, out_name, "POLYLINE", "",
                                        "ENABLED", "DISABLED", sr)
    arcpy.AddField_management(out_fc, "STEP_CNT", "LONG")
    arcpy.AddField_management(out_fc, "LEN_M", "DOUBLE")
    arcpy.AddField_management(out_fc, "MAX_SLOPE", "DOUBLE")

    length = 0.0
    worst = 0.0
    for i in range(1, pts.count):
        a = pts.getObject(i - 1)
        b = pts.getObject(i)
        dh = math.hypot(b.X - a.X, b.Y - a.Y)
        dv = b.Z - a.Z
        length += math.sqrt(dh * dh + dv * dv)
        if dh > 0:
            worst = max(worst, abs(dv) / dh)

    with arcpy.da.InsertCursor(out_fc, ["SHAPE@", "STEP_CNT", "LEN_M",
                                        "MAX_SLOPE"]) as ic:
        ic.insertRow((arcpy.Polyline(pts, sr, True, False),
                      len(path) - 1, length, worst))
    print(u"路径 -> %s：%d 步，三维长度 %.2f m，实际最大坡度 %.4g"
          % (out_fc, len(path) - 1, length, worst))
    if worst > max_slope + 1e-9:
        print(u"注意: 首尾点用的是你给的坐标，可能引入略超阈值的最后一步")
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
