"""CME Daily Bulletin Section 62 (Metal Futures OI) 解析器。

文件结构:每个商品(GC/SI/PL/PA/HG/MGC 等)一段,内含若干合约月的行
(月份+开盘+高/低+结算+点变化+Globex量+PNT量+OI+OI变化),末尾 TOTAL 行给出
该商品累计 OI 与当日变化。

自校验:逐月 OI 之和 == TOTAL 行的 OI;逐月变化之和 == TOTAL 行的变化。

验证结果(2026-05-27):贵金属+铜 100% OK,31/32 商品对账成功(UX 铀非项目品种)。
"""
from __future__ import annotations

import re

import pdfplumber

INT_RE = re.compile(r"^[\d,]+$")
HEAD_RE = re.compile(r"^([A-Z0-9][A-Z0-9]*)\s+FUT\s+(.+)$")
TOTAL_RE = re.compile(r"^TOTAL\s+([A-Z0-9][A-Z0-9]*)\s+FUT\b(.*)$")
MONTH_RE = re.compile(r"^([A-Z]{3}\d{2})\b")
LTD_TAIL = re.compile(r"^\d{2}/\d{2}")  # LTD 日历行(品种头后跟日期序列)


def _tail_oi_chg(toks: list[str]) -> tuple[int | None, int | None]:
    """从行尾抽 (OI, OI_chg)。

    支持五种结尾形态(按优先级匹配):
        ... <OI> UNCH                  → chg=0
        ... <OI>+ <chg> / <OI>- <chg>  → PDF 提取常把符号粘在前一个 token 上
        ... <OI> + <chg> / - <chg>     → 符号作为独立 token
        <number>                       → 单数字 TOTAL 行(全 UNCH 时 chg 被省略),作为 OI
        其它                            → 返回 (None, None)
    """
    if not toks:
        return None, None

    # 1) UNCH 结尾
    if toks[-1] == "UNCH":
        for t in reversed(toks[:-1]):
            if INT_RE.match(t):
                return int(t.replace(",", "")), 0
        return None, 0

    # 末尾必须是数字
    if not INT_RE.match(toks[-1]):
        return None, None
    last_num = int(toks[-1].replace(",", ""))
    head = toks[:-1]

    # 2) 符号粘在前一个 token 上,如 '3219+ 808' / '0- 116297'
    if head:
        gm = re.match(r"^([\d,]+)([+-])$", head[-1])
        if gm:
            chg = last_num if gm.group(2) == "+" else -last_num
            return int(gm.group(1).replace(",", "")), chg

    # 3) 符号作为独立 token,如 '... 19552 - 2786'
    if head and head[-1] in ("+", "-"):
        chg = last_num if head[-1] == "+" else -last_num
        for t in reversed(head[:-1]):
            if INT_RE.match(t):
                return int(t.replace(",", "")), chg
        return None, chg

    # 4) 单数字 TOTAL(全 UNCH 时 chg 被省略),如 'TOTAL AEP FUT 2747'
    return last_num, 0


def parse_section62(path: str) -> dict:
    """解析 Section62 PDF,返回各商品的结构化 OI 数据。

    返回 {code: {name, months, total_oi, total_oi_chg, status}},其中:
        code:       商品代码(GC/SI/PL/PA/MGC 等)
        name:       商品全称
        months:     list[{'month', 'oi', 'oi_chg'}]
        total_oi:   文件 TOTAL 行的累计 OI
        total_oi_chg: 文件 TOTAL 行的当日变化
        status:     'OK' / 'NO_TOTAL parsed=...' / 'PARSE_FAILED parsed=... vs TOTAL=...'
    """
    with pdfplumber.open(path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)

    out: dict[str, dict] = {}
    cur: str | None = None

    for raw in text.split("\n"):
        ln = raw.strip()
        if not ln:
            continue

        # 文件尾部的 "EX-PIT & OTHER BREAKDOWN" 子节有不同结构(EFP/EFS/BLOCKS 细分),
        # 里面也有月份码会被错误归到最后一个 cur_code。从此处起停止解析主 OI 数据。
        if "EX-PIT" in ln and "BREAKDOWN" in ln:
            break

        # TOTAL 行 — 注意要在 HEAD_RE 之前匹配,因为 HEAD_RE 会误匹配 "TOTAL XX FUT ..."
        m = TOTAL_RE.match(ln)
        if m:
            code = m.group(1)
            oi, chg = _tail_oi_chg(m.group(2).strip().split())
            if code in out:
                out[code]["total_oi"] = oi
                out[code]["total_oi_chg"] = chg
            continue

        # 商品头(过滤 LTD 日历行)
        m = HEAD_RE.match(ln)
        if m and not ln.startswith("TOTAL"):
            name = m.group(2).strip()
            if LTD_TAIL.match(name):
                continue
            cur = m.group(1)
            entry = out.setdefault(
                cur,
                {"name": name, "months": [], "total_oi": None, "total_oi_chg": None, "status": None},
            )
            entry["name"] = name
            continue

        # 合约月行
        if cur and MONTH_RE.match(ln):
            toks = ln.split()
            oi, chg = _tail_oi_chg(toks[1:])
            if oi is not None:
                out[cur]["months"].append({"month": toks[0], "oi": oi, "oi_chg": chg or 0})

    # —— 自校验 ——
    for code, d in out.items():
        sum_oi = sum(m["oi"] for m in d["months"])
        sum_chg = sum(m["oi_chg"] for m in d["months"])
        if d["total_oi"] is None:
            d["status"] = f"NO_TOTAL parsed={sum_oi}"
        elif sum_oi == d["total_oi"] and sum_chg == d["total_oi_chg"]:
            d["status"] = "OK"
        else:
            d["status"] = (
                f"PARSE_FAILED parsed={sum_oi}/{sum_chg:+} "
                f"vs TOTAL={d['total_oi']}/{d['total_oi_chg']:+}"
            )

    return out


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 2:
        print("usage: python -m cme_parsers.oi_section62 <path/to/Section62.pdf>")
        sys.exit(1)
    print(json.dumps(parse_section62(sys.argv[1]), ensure_ascii=False, indent=2))
