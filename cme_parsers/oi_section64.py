"""CME Daily Bulletin Section 64 (Metal Options OI) 解析器。

期权文件无文件级合计,做"按 `<CODE>_<CALL|PUT|OPT>` 聚合 OI 与变化"的紧凑摘要。
- CALL/PUT:细分方向的期权
- OPT:综合(部分微型或周期权用此标识)

复用 oi_section62 的 _tail_oi_chg 处理 TOTAL 行尾部数字。

验证结果(2026-05-27):28 个有 OI 商品全部抽出,贵金属+铜命名正确。
"""
from __future__ import annotations

import re

import pdfplumber

from .oi_section62 import _tail_oi_chg

HEAD_RE = re.compile(r"^([A-Z0-9][A-Z0-9]+)\s+(CALL|PUT|OPT)\s+(.+)$")
LTD_TAIL = re.compile(r"^\d{2}/\d{2}")


def parse_section64(path: str) -> dict:
    """解析 Section64 PDF,返回按 <CODE>_<SIDE> 聚合的期权 OI。

    返回 {f'{code}_{side}': {code, side, name, oi, oi_chg, n_total_rows}}
    其中 oi/oi_chg 是该商品该方向所有合约月 TOTAL 行的累加,n_total_rows 是参与累加
    的 TOTAL 行数(供 sanity 用)。

    注意:本解析器不返回 status,因为期权文件没有全局合计可供对账;上游若需"健康度"
    可基于 oi>0 数量、与昨天比较等做软校验。
    """
    with pdfplumber.open(path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)

    out: dict[str, dict] = {}
    cur_key: str | None = None

    for raw in text.split("\n"):
        ln = raw.strip()
        if not ln:
            continue

        m = HEAD_RE.match(ln)
        if m:
            name = m.group(3).strip()
            if LTD_TAIL.match(name):  # LTD 日历行,忽略
                continue
            cur_key = f"{m.group(1)}_{m.group(2)}"
            entry = out.setdefault(
                cur_key,
                {
                    "code": m.group(1),
                    "side": m.group(2),
                    "name": name,
                    "oi": 0,
                    "oi_chg": 0,
                    "n_total_rows": 0,
                },
            )
            entry["name"] = name  # 后到的真实名字覆盖前面的(确保 LTD 不污染)
            continue

        if ln.startswith("TOTAL") and cur_key:
            oi, chg = _tail_oi_chg(ln.split()[1:])
            if oi is not None:
                out[cur_key]["oi"] += oi
                out[cur_key]["oi_chg"] += chg or 0
                out[cur_key]["n_total_rows"] += 1

    return out


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 2:
        print("usage: python -m cme_parsers.oi_section64 <path/to/Section64.pdf>")
        sys.exit(1)
    print(json.dumps(parse_section64(sys.argv[1]), ensure_ascii=False, indent=2))
