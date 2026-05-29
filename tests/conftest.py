"""pytest 共享配置:定位 fixture 目录,并提供 session-scoped 已解析结果缓存。

Section64 是 71 页 PDF,每次解析约 20 秒。session-scoped 解析缓存让全套测试只解析
一次而不是每个测试一次,把 4 个 Section64 测试从 80+s 压到 ~22s。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 把 src/ 加入 sys.path,这样测试可以 `from cme_parsers.xxx import ...`
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

FIXTURES = Path(__file__).parent / "fixtures"


# —— 文件路径 fixture ——
@pytest.fixture(scope="session")
def silver_stocks_xls() -> Path:
    return FIXTURES / "Silver_stocks.xls"


@pytest.fixture(scope="session")
def issue_stop_pdf() -> Path:
    return FIXTURES / "MetalsIssuesAndStopsReport.pdf"


@pytest.fixture(scope="session")
def section62_pdf() -> Path:
    return FIXTURES / "Section62_Metals_Futures_2026-05-27.pdf"


@pytest.fixture(scope="session")
def section64_pdf() -> Path:
    return FIXTURES / "Section64_Metals_Option_2026-05-27.pdf"


@pytest.fixture(scope="session")
def cftc_long_pdf() -> Path:
    return FIXTURES / "CFTC_Long_Report.pdf"


# —— 已解析结果 fixture(慢的 PDF 只解析一次) ——
@pytest.fixture(scope="session")
def section64_result(section64_pdf):
    """Section64 的解析结果(整个测试会话共用一次)。"""
    from cme_parsers.oi_section64 import parse_section64
    return parse_section64(str(section64_pdf))
