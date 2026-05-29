"""Section64 期权 OI 解析器测试。

期权报告无文件级合计,这里锚定主要品种的聚合 OI 与名字正确性。
使用 session-scoped `section64_result` 缓存,4 个测试只解析一次 71 页 PDF。
"""
from __future__ import annotations

import re


def test_gold_options_present(section64_result):
    """OG CALL/PUT 必须存在,名字含 GOLD,OI 命中 5/27 已知值。"""
    r = section64_result
    assert "OG_CALL" in r and "OG_PUT" in r
    assert "GOLD" in r["OG_CALL"]["name"].upper()
    assert r["OG_CALL"]["oi"] == 371_362
    assert r["OG_PUT"]["oi"] == 152_709


def test_silver_options_present(section64_result):
    """SO CALL/PUT 必须存在,名字含 SILVER。"""
    r = section64_result
    assert "SO_CALL" in r and "SO_PUT" in r
    assert "SILVER" in r["SO_CALL"]["name"].upper()


def test_platinum_palladium_copper_options(section64_result):
    """铂金/钯金/铜期权命名正确。"""
    r = section64_result
    assert "PLATINUM" in r["PO_CALL"]["name"].upper()
    assert "PALLADIUM" in r["PAO_CALL"]["name"].upper()
    assert "COPPER" in r["HX_CALL"]["name"].upper()


def test_no_ltd_calendar_pollution(section64_result):
    """所有商品 name 不能像 LTD 日历(以 MM/DD 形式开头)。"""
    for k, v in section64_result.items():
        assert not re.match(r"^\d{2}/\d{2}", v["name"]), (
            f"{k} name looks like LTD calendar: {v['name']!r}"
        )
