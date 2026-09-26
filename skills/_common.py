# -*- coding: utf-8 -*-
"""
yghsBridge ArcMap skills 公共库（py2.7 兼容）。

供各技能 scripts/run.py 通过 execute_code 或独立执行复用。
约定：
- 所有函数接收/返回 unicode 字符串（py2.7 下中文路径/字段安全）。
- 读 xlsx 映射表用 xlrd（本环境已装，支持 xlsx）。
- 面积/长度单位换算集中在此，避免各脚本各自写错。
"""
import os
import sys
import arcpy


# ---- skills 根目录（供各 run.py 定位 resources 映射表）----
# 关键：通过桥 execute_code 的 exec() 执行 run.py 时，run.py 自身的 __file__
# 未定义，不能用 os.path.abspath(__file__) 定位资源。而 _common 是 import 进来的，
# __file__ 始终有效，故统一从 _common.__file__ 推导 skills 根目录。
SKILLS_ROOT = os.path.dirname(os.path.abspath(__file__))


def skill_dir(skill_name):
    """返回指定 skill 的目录绝对路径（unicode）。"""
    return os.path.join(SKILLS_ROOT, skill_name)


def resource_path(skill_name, *parts):
    """返回 skill 下 resources/... 的绝对路径（unicode）。"""
    return os.path.join(SKILLS_ROOT, skill_name, u'resources', *parts)


def _to_unicode(s):
    """把任意字符串安全转成 unicode（py2.7 兼容，处理 gbk 字节串）。"""
    if isinstance(s, unicode):
        return s
    if isinstance(s, str):
        try:
            return s.decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            try:
                return s.decode('gbk')
            except (UnicodeDecodeError, UnicodeEncodeError):
                return s.decode('latin-1')
    return unicode(s)


# ---- stdout 保护：容忍 arcpy 的 GBK 中文 warning 直跑时不崩 ----
class _Utf8Stdout(object):
    """把 stdout 换成 UTF-8 writer，对 str(gbk)/unicode 都能安全写出。

    arcpy 在 py2.7 直跑时会输出 GBK 编码的中文 warning（如 code page 提示），
    若 stdout 是默认编码会 UnicodeDecodeError。execute_code 通道里 runner 已垫
    一层，这里再垫一层保证独立执行也不崩。
    """
    def write(self, data):
        # unicode -> utf-8 bytes；str(bytes) -> 直接透传（避免 gbk/utf8 混编崩溃）
        if isinstance(data, unicode):
            data = data.encode('utf-8')
        # else: 原样 bytes 透传（可能是 gbk，让调用方自己保证）
        try:
            self._w.write(data)
        except Exception:
            pass

    def flush(self):
        try:
            self._w.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._w, name)


def _patch_stdout():
    if not getattr(sys.stdout, '_yghs_patched', False):
        wrapper = _Utf8Stdout()
        wrapper._w = sys.stdout
        wrapper._yghs_patched = True
        sys.stdout = wrapper
        sys.stderr = wrapper


_patch_stdout()


# ---- argv 规范化：命令行传入的中文参数是 gbk 字节串，arcpy.da 需 unicode 路径 ----
def _patch_argv():
    for i in range(len(sys.argv)):
        sys.argv[i] = _to_unicode(sys.argv[i])


_patch_argv()

# ---- 单位换算系数 ----
UNIT_FACTOR = {
    u'平方米': 1.0,
    u'公顷': 10000.0,
    u'公顷（hm2）': 10000.0,
    u'平方公里': 1000000.0,
    u'亩': 666.6666666667,
}


def unit_factor(unit_name):
    """单位名 -> 换算系数（面积值 / 系数 = 目标单位值）。

    精确匹配单位名，默认平方米（系数 1.0）。原实现用 ``k in (unit_name or ...)``
    的字符串子串判断，属逻辑缺陷（如传 '平方公里/公顷' 会先命中第一个子串匹配项）。
    """
    return UNIT_FACTOR.get(unit_name, 1.0)


def is_gdb_path(p):
    """判断是否 .gdb 路径（按路径末尾的 .gdb 段精确匹配，避免目录名含 .gdb 误判）。"""
    p = (p or u'').strip()
    if not p:
        return False
    return p.lower().rstrip(u'\\/').endswith(u'.gdb')


def field_exists(dataset, field):
    """数据集（图层/要素类/表）里是否存在字段（容忍中文名）。"""
    try:
        names = [f.name for f in arcpy.ListFields(dataset)]
        return field in names
    except Exception:
        return False


def ensure_field(dataset, field, ftype=u'TEXT', length=50, alias=None):
    """字段不存在则新增，返回字段名。"""
    if not field_exists(dataset, field):
        arcpy.AddField_management(dataset, field, ftype, field_length=length,
                                  field_alias=alias or field)
    return field


def read_xlsx_dict(xlsx_path, sheet_index=0, key_col=0, val_col=1, header_rows=1):
    """读 xlsx 映射表 -> {键: 值} 字典（跳过前 header_rows 行表头）。

    返回 dict（unicode 键值）；键值均做 strip。空键跳过。
    """
    import xlrd
    book = xlrd.open_workbook(xlsx_path)
    sh = book.sheet_by_index(sheet_index)
    d = {}
    for r in range(header_rows, sh.nrows):
        k = sh.cell_value(r, key_col)
        v = sh.cell_value(r, val_col)
        if k is None:
            continue
        k = (unicode(k) if not isinstance(k, unicode) else k).strip()
        v = (unicode(v) if not isinstance(v, unicode) else v).strip()
        if k == u'':
            continue
        d[k] = v
    return d


def read_xlsx_sheet_names(xlsx_path):
    import xlrd
    book = xlrd.open_workbook(xlsx_path)
    return [book.sheet_by_index(i).name for i in range(book.nsheets)]


# 对外安全转换（脚本里对 cursor 读出的字段值统一包一层 S()）
def S(s):
    return _to_unicode(s)


class UnicodeCsvWriter(object):
    """py2.7 安全的 CSV writer：写 unicode 中文自动编 utf-8，不再 ascii 崩溃。"""
    def __init__(self, csvfile):
        import csv
        self._w = csv.writer(csvfile)

    def writerow(self, row):
        enc = []
        for x in row:
            if isinstance(x, unicode):
                enc.append(x.encode('utf-8'))
            elif isinstance(x, str):
                # 已是 bytes，先转 unicode 再编 utf-8（防 gbk/utf8 混）
                enc.append(_to_unicode(x).encode('utf-8'))
            else:
                enc.append(x)
        self._w.writerow(enc)


def log(msg):
    """中文安全输出（py2.7 stdout 字节流，unicode 需 encode utf-8）。"""
    msg = _to_unicode(msg)
    sys.stdout.write(msg.encode('utf-8') + '\n')


def log_u(msg):
    """直接打印 unicode（仅在已垫 stdout 包装时安全）。"""
    print(msg)


def is_geographic(dataset):
    """判断数据集坐标系是否为地理坐标系（无投影）。"""
    try:
        sr = arcpy.Describe(dataset).spatialReference
        return (sr is not None) and (str(getattr(sr, 'type', u'')).lower() == u'geographic')
    except Exception:
        return False


def area_expr(area_type=u'投影', dataset=None):
    """按面积类型返回面积字段表达式片段（单位：平方米）。

    - area_type='椭球' 或数据集为地理坐标系（无投影）时，用测地面积
      !shape.geodesicArea!（返回平方米，避免平方度被误当平方米）。
    - 投影坐标系下 area_type='投影' 用 !shape.area!（也是平方米）。
    """
    if area_type == u'椭球' or is_geographic(dataset):
        return u'!shape.geodesicArea!'
    return u'!shape.area!'


def length_expr(dataset=None):
    """返回长度字段表达式片段（单位：米）。

    地理坐标系下用 !shape.geodesicLength!（米），投影坐标系用 !shape.length!（米）。
    """
    if is_geographic(dataset):
        return u'!shape.geodesicLength!'
    return u'!shape.length!'


# ---- 三调 DLBM 三大类归并规则（源自 plan-statistics-s-d-l 原版 SQL，权威）----
# 归并到 8 类：耕地/园地/林地/草地/其它用地/建设用地/未利用地/农用地
SD_SQL = {
    u'GDMJ': u"DLBM IN ('0101','0102','0103')",
    u'LDMJ': u"DLBM IN ('0301','0301K','0302','0302K','0303','0304','0305','0306','0307','0307K')",
    u'CDMJ': u"DLBM IN ('0401','0403','0403K','0404')",
    u'YDMJ': u"DLBM IN ('0201','0201K','0202','0202K','0203','0203K','0204','0204K')",
    u'QTYDMJ': u"DLBM IN ('1006','1103','1104','1104A','1104K','1107','1107A','1202','1203','0402')",
    u'JSYDMJ': u"DLBM IN ('05H1','0508','0601','0602','0603','0701','0702','08H1','08H2','08H2A','0809','0810','0810A','09','1001','1002','1003','1004','1005','1007','1008','1009','1109','1201')",
    u'WLYDMJ': u"DLBM IN ('1101','1102','1105','1106','1108','1110','1204','1205','1206','1207','1208')",
    u'NYDMJ': u"DLBM IN ('0404','0101','0102','0103','0201','0201K','0202','0202K','0203','0203K','0204','0204K','0301','0301K','0302','0302K','0303','0304','0305','0306','0307','0307K','0401','0402','0403','0403K','1006','1103','1104','1104A','1104K','1107','1107A','1202','1203')",
}

# 三大类别名（用于输出表头/字段别名）
SD_ALIAS = {
    u'GDMJ': u'耕地面积', u'YDMJ': u'园地面积', u'LDMJ': u'林地面积', u'CDMJ': u'草地面积',
    u'QTYDMJ': u'其它用地面积', u'JSYDMJ': u'建设用地面积', u'WLYDMJ': u'未利用地面积',
    u'NYDMJ': u'农用地面积',
}


# 从 SD_SQL 的 "DLBM IN ('a','b',...)" 里抽出编码集合，供精确成员判断。
# 原实现用 ``if dlbm in sql`` 子串匹配，短码/脏码（如 '101'、'05'）会误归并到错误大类。
# 注意：NYDMJ（农用地）是下位大类的并集（上位概念），必须最后兜底判断，
# 否则无序 dict 迭代下会把耕地/园地等误归到农用地。
SD_CODES = {}
for _code, _sql in SD_SQL.items():
    _start = _sql.find(u'(')
    _end = _sql.rfind(u')')
    if _start != -1 and _end > _start:
        _codes = set(x.strip().strip(u"'") for x in _sql[_start + 1:_end].split(u',') if x.strip())
        SD_CODES[_code] = _codes

# 有优先级的下位大类判定顺序（先细分，最后才是上位类「农用地」）。
_SD_CLASSIFY_ORDER = [
    u'GDMJ', u'YDMJ', u'LDMJ', u'CDMJ', u'JSYDMJ', u'WLYDMJ', u'QTYDMJ', u'NYDMJ',
]


def sd_classify(dlbm):
    """单条 DLBM -> 三大类代码（GDMJ/LDMJ/...），未命中返回 None。

    按下位大类优先、农用地兜底的固定顺序做精确编码成员判断，O(8) 每次。
    """
    if dlbm is None:
        return None
    dlbm = (dlbm if isinstance(dlbm, unicode) else unicode(dlbm)).strip()
    for code in _SD_CLASSIFY_ORDER:
        if dlbm in SD_CODES.get(code, ()):
            return code
    return None
