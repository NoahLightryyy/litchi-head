"""辩论图的数据采集节点与采集后的路由（自 orchestrator.py 拆出，逻辑未改）。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from src.data.collector import DataCollector, format_market_brief
from src.data.evidence import (
    EvidenceCapability,
    EvidenceEnvelope,
    EvidenceRequest,
)
from src.data.evidence_service import DataEvidenceService
from src.data.kline_business import (
    KlineBusinessEnvelope,
    KlineBusinessFailure,
)
from src.data.models import FinancialMetrics, KLine, NewsItem, StockQuote
from src.data.news_runtime import NEWS_EVIDENCE_POLICY, NEWS_WINDOW
from src.data.quote_runtime import (
    RealtimeQuoteEvidenceService,
)
from src.data.research_policy import RESEARCH_QUOTE_POLICY
from src.debate.graph_state import (
    DebateState,
    _evidence_limitation,
    _format_evidence_limitation_notice,
    _must_block_reasoning,
)
from src.debate.kline_context import (
    KlineBusinessProvider,
    classify_kline_business_result,
    format_kline_business_context,
    kline_evidence_reference,
    kline_failure_limitation,
)
from src.debate.models import (
    InstrumentResearchContext,
)
from src.debate.research_evidence import (
    closing_research_quotes,
    partial_research_news,
)

logger = logging.getLogger("src.debate.orchestrator")


# ── 节点函数 ──────────────────────────────────────────────────────


def collect_data_node(
    state: DebateState,
    collector: DataCollector,
    news_evidence_service: DataEvidenceService | None = None,
    quote_evidence_service: RealtimeQuoteEvidenceService | None = None,
    kline_business_provider: KlineBusinessProvider | None = None,
    research_supplement: Callable[[str], str] | None = None,
    prepared_research: InstrumentResearchContext | None = None,
) -> dict:
    """数据采集节点 —— 从 DataCollector 获取行情 + K线 + 新闻

    Args:
        state: 当前辩论状态
        collector: DataCollector 实例

    Returns:
        State 更新，写入 market_data
    """
    inp = state.get("debate_input", {})
    code = inp.get("stock_code", "")
    if inp.get("instrument_type", "stock") == "etf":
        if (
            prepared_research is None
            or prepared_research.stock_code != code
            or prepared_research.stock_name != inp.get("stock_name")
        ):
            return {
                "evidence_failure_kind": "detail",
                "evidence_envelope": {
                    "capability": "etf_research",
                    "error_codes": ["instrument_identity_conflict"],
                },
                "errors": ["EVIDENCE_INCOMPLETE"],
            }
        return {
            "market_data": {
                "brief": prepared_research.brief,
                "industry": prepared_research.industry,
                "chain_position": "ETF主题与组合",
                "instrument_type": "etf",
            },
            "evidence_limitations": [
                item.model_dump(mode="json") for item in prepared_research.evidence_limitations
            ],
        }
    quote_evidence_envelope: EvidenceEnvelope | None = None
    news_evidence_envelope: EvidenceEnvelope | None = None
    evidence_limitations: list[dict[str, object]] = []
    evidence_references: list[dict[str, object]] = []
    kline_business_envelope: KlineBusinessEnvelope | None = None
    kline_context = ""

    if kline_business_provider is not None:
        kline_result = kline_business_provider(code)
        if kline_result.symbol != code:
            return {
                "evidence_failure_kind": "detail",
                "evidence_envelope": {
                    "capability": "kline_business",
                    "error_codes": ["instrument_identity_conflict"],
                    "requested_symbol": code,
                    "received_symbol": kline_result.symbol,
                    "collected_at": kline_result.as_of.isoformat(),
                },
                "errors": ["EVIDENCE_INCOMPLETE"],
            }
        kline_classification = classify_kline_business_result(kline_result)
        if kline_classification == "blocked":
            return {
                "evidence_failure_kind": "kline_business",
                "evidence_envelope": kline_result.model_dump(mode="json"),
                "errors": ["EVIDENCE_INCOMPLETE"],
            }
        if isinstance(kline_result, KlineBusinessFailure):
            evidence_limitations.append(kline_failure_limitation(kline_result))
        else:
            kline_business_envelope = kline_result
            kline_context = format_kline_business_context(kline_result)
            evidence_references.append(kline_evidence_reference(kline_result))

    logger.info("Debate collection started: symbol=%s", code)
    if quote_evidence_service is not None and kline_business_provider is None:
        quote_request = EvidenceRequest(
            capability=EvidenceCapability.REALTIME_QUOTE,
            stock_code=code,
            stock_name=inp.get("stock_name", ""),
        )
        quote_evidence_envelope = quote_evidence_service.collect(
            quote_request,
            RESEARCH_QUOTE_POLICY,
        )
        if not quote_evidence_envelope.complete:
            if _must_block_reasoning(quote_evidence_envelope):
                return {
                    "evidence_envelope": quote_evidence_envelope.model_dump(mode="json"),
                    "errors": ["EVIDENCE_INCOMPLETE"],
                }
            evidence_limitations.append(
                _evidence_limitation(quote_evidence_envelope)
            )

    logger.info("Debate quote evidence collected: symbol=%s", code)
    if news_evidence_service is not None:
        end_at = datetime.now(UTC)
        request = EvidenceRequest(
            capability=EvidenceCapability.NEWS,
            stock_code=code,
            stock_name=inp.get("stock_name", ""),
            start_at=end_at - NEWS_WINDOW,
            end_at=end_at,
        )
        news_evidence_envelope = news_evidence_service.collect(
            request,
            NEWS_EVIDENCE_POLICY,
        )
        if not news_evidence_envelope.complete:
            if _must_block_reasoning(news_evidence_envelope):
                return {
                    "evidence_envelope": news_evidence_envelope.model_dump(mode="json"),
                    "errors": ["EVIDENCE_INCOMPLETE"],
                }
            evidence_limitations.append(
                _evidence_limitation(news_evidence_envelope)
            )

    logger.info("Debate news evidence collected: symbol=%s", code)
    quotes: list[StockQuote] = []
    klines: list[KLine] = []
    news: list[NewsItem] = []
    financial_data: list[FinancialMetrics] = []

    if kline_business_envelope is not None:
        quotes = [kline_business_envelope.live_quote]
    elif quote_evidence_envelope is not None:
        quotes = [
            StockQuote.model_validate(item)
            for item in quote_evidence_envelope.items
        ]
        if not quote_evidence_envelope.complete:
            research = closing_research_quotes(quote_evidence_envelope, datetime.now(UTC))
            if research.quotes:
                quotes = research.quotes
            for limitation in evidence_limitations:
                if limitation["capability"] == "realtime_quote" and research.note:
                    limitation["research_note"] = research.note
    else:
        try:
            quotes = collector.get_realtime_quotes()
        except Exception as e:
            logger.exception("行情数据获取失败: %s", e)

    if kline_business_envelope is not None:
        # Do not coerce the Decimal QFQ series into the legacy integer-volume KLine
        # model. The exact frozen series is rendered by format_kline_business_context.
        klines = []
    elif kline_business_provider is None:
        try:
            klines = collector.get_klines(code, period="daily", start="", end="")
        except Exception as e:
            logger.exception("K线数据获取失败 [%s]: %s", code, e)

    if news_evidence_envelope is not None:
        news = [
            NewsItem.model_validate(item)
            for item in news_evidence_envelope.items
        ]
        partial_news = partial_research_news(news_evidence_envelope)
        existing = {(item.source_id, item.code, item.title) for item in news}
        for item in partial_news.items:
            identity = (item.source_id, item.code, item.title)
            if identity not in existing:
                news.append(item)
                existing.add(identity)
        for limitation in evidence_limitations:
            if limitation["capability"] == "news" and partial_news.note:
                limitation["research_note"] = partial_news.note
    else:
        try:
            news = collector.get_news(code)
        except Exception as e:
            logger.exception("新闻数据获取失败 [%s]: %s", code, e)

    logger.info("Debate klines collected; fetching financials: symbol=%s", code)
    try:
        financial_data = collector.get_financials(code)
    except Exception as e:
        logger.exception("财务数据获取失败 [%s]: %s", code, e)

    logger.info("Debate financials collected; fetching indicators: symbol=%s", code)
    # PD-005: 获取行业分类 + 产业链位置 + 关键指标
    industry_name = ""
    chain_pos = ""
    key_indicators: list[dict] = []
    try:
        di = collector.get_dynamic_indicators(code)
        if di:
            raw_indicators = di.get("indicators", [])
            industry_name = str(di.get("industry", ""))
            chain_pos = str(di.get("chain_position", ""))
            key_indicators = list(raw_indicators) if isinstance(raw_indicators, list) else []
    except Exception as e:
        logger.exception("动态指标获取失败 [%s]: %s", code, e)

    # 按个股过滤行情
    target_quote: StockQuote | None = None
    for q in quotes:
        if q.code == code:
            target_quote = q
            break

    logger.info("Debate indicators collected; fetching sentiment: symbol=%s", code)
    # 辅助市场情绪只读有效缓存；单股分析不能等待全市场目录/分页抓取。
    sentiment: object | None = None
    try:
        sentiment = collector.get_cached_market_sentiment()
    except Exception as e:
        logger.exception("市场情绪获取失败: %s", e)

    logger.info("Debate collection finished: symbol=%s", code)
    # 生成市场简报（含 PD-005 行业分析层 + C2 情绪层）
    brief = format_market_brief(
        stock_code=code,
        stock_name=inp.get("stock_name", ""),
        quote=target_quote,
        klines=klines,
        news=news,
        financials=financial_data,
        industry=industry_name,
        chain_position=chain_pos,
        key_indicators=key_indicators,
        sentiment=sentiment,
        quote_volume_unit="股" if quote_evidence_envelope is not None else "手",
    )
    from src.debate.archive_research import research_context

    archive_coverage: list[dict] = []
    try:
        archive_context, archive_coverage = research_context(code, inp.get("stock_name", ""))
        brief += "\n\n" + archive_context
    except Exception:
        logger.exception("Archive research retrieval failed: %s", code)
        brief += "\n新闻历史库检索失败，不能假定历史新闻覆盖完整。"
    if research_supplement is not None:
        try:
            brief += "\n\n" + research_supplement(code)
        except Exception:
            logger.exception("Active research supplementation failed: %s", code)
            brief += "\n主动补证失败，相关缺口仍然存在。"
    if kline_context:
        brief = f"{kline_context}\n\n{brief}"
    if evidence_limitations:
        brief = f"{_format_evidence_limitation_notice(evidence_limitations)}\n\n{brief}"

    result: dict[str, object] = {
        "market_data": {
            "brief": brief,
            "industry": industry_name,
            "chain_position": chain_pos,
            "quote": target_quote.model_dump() if target_quote else None,
            "quotes": [q.model_dump() for q in quotes],
            "klines": [k.model_dump() for k in klines],
            "news": [n.model_dump() for n in news],
            "news_archive_coverage": archive_coverage,
            "financials": [f.model_dump() for f in financial_data],
            "kline_business": (
                kline_business_envelope.model_dump(mode="json")
                if kline_business_envelope is not None
                else None
            ),
        },
    }
    evidence_envelope = news_evidence_envelope or quote_evidence_envelope
    if evidence_envelope is not None:
        result["evidence_envelope"] = evidence_envelope.model_dump(mode="json")
    if evidence_limitations:
        result["evidence_limitations"] = evidence_limitations
    if evidence_references:
        result["evidence_references"] = evidence_references
    return result


def _route_after_collection(state: DebateState) -> str:
    """Continue on disclosed gaps; stop only corrupted/conflicted evidence."""
    return (
        "stop"
        if "EVIDENCE_INCOMPLETE" in state.get("errors", [])
        else "continue"
    )


def _route_after_reasoning(state: DebateState) -> str:
    """Allow labelled reasoning but never pass incomplete evidence into trading."""
    return "stop" if state.get("evidence_limitations", []) else "risk"
