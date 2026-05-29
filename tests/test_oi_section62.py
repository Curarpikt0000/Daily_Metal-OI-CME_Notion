"""Section62 期货 OI 解析器测试。

锚定 2026-05-27 文件的贵金属+铜真实 OI 值。
"""
from __future__ import annotations

from cme_parsers.oi_section62 import parse_section62


def test_precious_metals_all_ok(section62_pdf):
    """贵金属 + 铜核心品种必须全部 status=OK。"""
    r = parse_section62(str(section62_pdf))
    for code in ("GC", "SI", "PL", "PA", "HG", "MGC", "SIL"):
        assert code in r, f"{code} not parsed"
        assert r[code]["status"] == "OK", f"{code}: {r[code]['status']}"


def test_gc_known_totals(section62_pdf):
    """5/27 GC(黄金主合约): TOTAL OI=355,799, chg=-10,712。"""
    r = parse_section62(str(section62_pdf))
    assert r["GC"]["total_oi"] == 355_799
    assert r["GC"]["total_oi_chg"] == -10_712
    assert r["GC"]["name"].startswith("COMEX GOLD")


def test_si_known_totals(section62_pdf):
    """5/27 SI(白银主合约): TOTAL OI=102,053, chg=+602。"""
    r = parse_section62(str(section62_pdf))
    assert r["SI"]["total_oi"] == 102_053
    assert r["SI"]["total_oi_chg"] == 602


def test_at_least_31_ok(section62_pdf):
    """整体健康度: 至少 31 个商品 status=OK(允许 UX 铀失败)。"""
    r = parse_section62(str(section62_pdf))
    ok = sum(1 for d in r.values() if d["status"] == "OK")
    assert ok >= 31, f"only {ok} OK out of {len(r)}"
