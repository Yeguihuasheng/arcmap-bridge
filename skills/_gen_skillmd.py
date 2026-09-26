# -*- coding: utf-8 -*-
"""
批量生成 ArcMap 版 SKILL.md：读 Pro 版 SKILL.md 提取核心信息，
套 ArcMap 通道模板（execute_code + scripts/run.py）。
"""
import os
import io
import re

SRC = r'A:\GisProTest\opensource\arcgis-pro-bridge\skills'
DST = r'A:\GisProTest\.arcmapbridge\skills'

# 每个 skill 的 run.py 用法说明（命令行参数，供 AI 问询后拼装）
USAGE = {
    'plan-remove0-d-m': u'run.py <图层> <字段名>',
    'plan-supply0-d-m': u'run.py <图层> <字段名> <目标位数LEN>',
    'plan-s-d-changer': u'run.py <图层> <DLBM字段> <DLMC字段> <模式:DLBM转DLMC|DLMC转DLBM>',
    'plan-create-grad-y-d-y-h': u'run.py <图层> <编码字段BM> <分级数1|2|3> <版本:旧版|新版> <是否生成名称:是|否>',
    'plan-y-d-y-h-old2-new': u'run.py <图层> <旧编码字段oldBM> <新编码字段newBM> <新名称字段newMC>',
    'plan-s-d2-y-d-y-h': u'run.py <图层> <三调名称字段DLMC> <目标字段> <转换类型:通用|待细分转一级类|全部转一级类> <版本:旧版|新版>',
    'plan-y-d-y-h-changer': u'run.py <图层> <源字段> <目标字段> <模式:代码转名称|名称转代码> <版本:旧版|新版>',
    'plan-updata-y-d-y-h': u'run.py <图层> <编码字段> <名称字段> <用地用海合并值(如01耕地)> [SQL筛选]',
    'plan-check-y-d-change': u'run.py <现状图层> <规划图层> <现状字段> <规划字段> <输出要素类>',
    'plan-general-statistic': u'run.py <图层> <面积字段> <分组字段;分隔> <单位> <输出CSV> [小数位]',
    'plan-multi-statistics': u'run.py <分区图层> <分区字段> <面积类型:投影|椭球> <单位> <输出CSV> <图层1> [图层2...]',
    'plan-multi-statistics-y-d': u'run.py <分区图层> <分区字段> <面积类型> <单位> <输出CSV> <图层> <扣除系数字段>',
    'plan-statistic-load': u'run.py <道路线图层> <道路类型字段> <范围面图层> <输出CSV>',
    'plan-statistics-s-d-l': u'run.py <三调图层> <DLBM字段> <分区图层|空> <面积类型> <单位> <输出CSV> [指标字段]',
    'plan-statistics-y-d-y-h': u'run.py <图层> <编码字段> <面积字段> <单位> <分级:大类|中类|小类> <输出CSV> [分区图层] [分区字段]',
    'plan-statistics-x-z-g-h': u'run.py <现状图层> <规划图层> <编码字段> <面积字段> <单位> <分级> <输出CSV>',
    'plan-s-q-s-x-statistics': u'run.py <分区图层> <分区字段> <开发边界> <永基农田> <生态红线> <面积类型> <单位> <输出CSV> [扣减系数字段]',
    'territory-z-y1': u'run.py <mode:地类统计|三大类归并|编码转换> <图层> <字段> <单位> <输出CSV> [面积字段]',
    'gdb-truncate-data': u'run.py <GDB路径> [是否含独立要素类:是|否]',
    'plan-line-to-road': u'run.py <中心线图层> <红线宽度米> <路缘石内缩米> <输出GDB> <红线名> <路缘石线名> <中心线名>',
    'plan-create-road-intersection': u'run.py <道路中心线图层> <输出GDB> <输出要素类名>',
}

# 降级说明（纯几何引擎 skill）
DOWNGRADE = {
    'plan-line-to-road': u'⚠ 原版为 Pro SDK GeometryEngine 精确几何（线偏移/圆角/交叉口），本脚本为 Buffer 近似降级实现。',
    'plan-create-road-intersection': u'⚠ 原版为 Pro SDK 精确几何（交点打断/转弯半径圆角），本脚本为 Intersect 交点近似降级实现。',
}


def extract_section(text, header):
    """提取某 ## 章节的正文（到下一个 ## 或 EOF）。"""
    m = re.search(r'^## %s[^\n]*\n(.*?)(?=^## |\Z)' % re.escape(header), text, re.S | re.M)
    return m.group(1).strip() if m else ''


def extract_frontmatter(text):
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    return m.group(1) if m else ''


def main():
    for name in sorted(os.listdir(SRC)):
        sdir = os.path.join(SRC, name)
        skill_md = os.path.join(sdir, 'SKILL.md')
        if not os.path.isfile(skill_md):
            continue
        src_text = io.open(skill_md, encoding='utf-8-sig').read()

        # 提取 name_zh
        m_zh = re.search(r'^name_zh:\s*(.+)$', src_text, re.M)
        name_zh = m_zh.group(1).strip() if m_zh else name

        # 提取 frontmatter 里的 description_zh
        m_desc = re.search(r'^description_zh:\s*(.+)$', src_text, re.M)
        desc_zh = m_desc.group(1).strip() if m_desc else ''
        desc_zh = desc_zh.replace(u'ArcGIS Pro', u'ArcMap').replace(u'ArcProBridge', u'yghsBridge ArcMap')

        # 提取问询清单章节
        ask_section = extract_section(src_text, u'使用前必须先问询')
        # 提取原始实现要点
        impl = extract_section(src_text, u'原始实现要点')
        if not impl:
            impl = extract_section(src_text, u'详细说明')
        # 提取功能
        func = extract_section(src_text, u'功能')

        usage = USAGE.get(name, u'（见 scripts/run.py 顶部注释）')
        downgrade = DOWNGRADE.get(name, u'')

        new_md = u"""---
name: {name}
name_zh: {name_zh}
description_zh: {desc_zh}
user-invocable: true
---

# {name_zh}

## 功能
{func}

## 使用前必须先问询（缺一不可）
{ask_section}

## 执行路径（ArcMap 版）
本技能经 **yghsBridge ArcMap 桥接**执行：AI 按上方问询清单逐项确认参数后，
把参数代入执行脚本 `scripts/run.py`，经桥的 `execute_code` 通道（py2.7 arcpy）在 ArcMap 内执行。

脚本用法：
```
{usage}
```
{downgrade}
执行完成后读回输出行数/抽查字段值/确认成果文件非空。

## 原始实现要点（参考，源自 Pro 版）
{impl}
""".format(name=name, name_zh=name_zh, desc_zh=desc_zh, func=func,
           ask_section=ask_section, usage=usage, downgrade=downgrade, impl=impl)

        dst_file = os.path.join(DST, name, 'SKILL.md')
        io.open(dst_file, 'w', encoding='utf-8-sig').write(new_md)
        print('生成', name)

    print('完成')


if __name__ == '__main__':
    main()
