"""Deterministic affordability preview; trusted attestations are server-side only."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal, localcontext
from zoneinfo import ZoneInfo

from backend.policy_capital_contract import (
    EvidencePackage,
    ExecutionPreview,
    ExecutionRequest,
    FeeSchedule,
    TradingRule,
)


@dataclass(frozen=True)
class VerifiedExecutionContext:
    """Created only by a server verifier, never deserialized from client input.

    Production has no account/fee verifier yet and therefore cannot return ready.
    Each attestation binds the account evidence to the exact instrument and quote.
    """

    package: EvidencePackage
    symbol: str
    market: str
    instrument_kind: str
    rules: TradingRule
    fees: FeeSchedule
    permission_evidence_reference: str
    cash_available_cny: Decimal
    cash_evidence_reference: str
    verified_at: datetime
    valid_until: datetime
    quote_at: datetime
    max_quote_age: timedelta


ContextResolver = Callable[[ExecutionRequest], VerifiedExecutionContext | None]


def calculate_preview(
    request: ExecutionRequest,
    context: VerifiedExecutionContext | None = None,
    *,
    now: datetime | None = None,
) -> ExecutionPreview:
    """Return zero numerical outputs unless every required boundary is verified."""
    current = now or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        return ExecutionPreview(
            status="blocked",
            evidence_package_id=request.evidence_package_id,
            quantity=None,
            estimated_cost=None,
            remaining_cash=None,
            gaps=["测算时间缺少时区"],
        )
    gaps: list[str] = []
    decimals = [request.cash_available_cny, request.user_budget_cny, request.limit_price_cny]
    if context:
        decimals.extend(
            [
                context.cash_available_cny,
                context.rules.price_tick_cny,
                context.fees.commission_rate,
                context.fees.minimum_commission_cny,
                context.fees.additional_rate,
                context.fees.additional_fixed_cny,
            ]
        )
    if request.rules:
        decimals.append(request.rules.price_tick_cny)
    if request.fees:
        decimals.extend(
            [
                request.fees.commission_rate,
                request.fees.minimum_commission_cny,
                request.fees.additional_rate,
                request.fees.additional_fixed_cny,
            ]
        )
    if any(
        v is not None
        and (not v.is_finite() or abs(v.adjusted()) > 100 or len(v.as_tuple().digits) > 100)
        for v in decimals
    ):
        return ExecutionPreview(
            status="blocked",
            evidence_package_id=request.evidence_package_id,
            quantity=None,
            estimated_cost=None,
            remaining_cash=None,
            gaps=["金额或费率精度超出测算支持范围，请使用合理金额和精度"],
        )
    for name, label in (
        ("cash_available_cny", "可用现金"),
        ("user_budget_cny", "本次预算"),
        ("limit_price_cny", "限价"),
        ("quote_at", "行情时间"),
        ("rules", "有效交易规则"),
        ("fees", "完整客户费用"),
    ):
        if getattr(request, name) is None:
            gaps.append(f"缺少{label}")
    if request.permission_confirmed is not True:
        gaps.append("缺少账户交易权限确认")
    if context is None:
        gaps.extend(
            [
                "服务端尚未核验账户交易权限，请补充有效权限证明",
                "服务端尚未核验可用现金，请补充账户资金证明",
                "服务端尚未核验完整客户费用，请补充券商费用协议",
                "服务端尚未核验行情时效与适用交易规则",
            ]
        )
    else:
        package = context.package
        if (
            package.package_id != request.evidence_package_id
            or package.subject_id != request.symbol
            or package.subject_kind != request.instrument_kind
            or (context.symbol, context.market, context.instrument_kind)
            != (request.symbol, request.market, request.instrument_kind)
        ):
            gaps.append("标的身份与服务端证据不匹配")
        if request.rules != context.rules or request.fees != context.fees:
            gaps.append("客户端规则或费用与服务端核验版本不一致")
        if not any(
            e.id == context.rules.evidence_id and e.role in {"primary", "official_repost"}
            for e in package.evidence
        ):
            gaps.append("交易规则缺少包内官方证据")
        if (
            not context.permission_evidence_reference.strip()
            or not context.cash_evidence_reference.strip()
        ):
            gaps.append("缺少账户权限或资金证明")
        dates = (context.verified_at, context.valid_until, context.quote_at)
        if any(d.tzinfo is None or d.utcoffset() is None for d in dates):
            return ExecutionPreview(
                status="blocked",
                evidence_package_id=request.evidence_package_id,
                quantity=None,
                estimated_cost=None,
                remaining_cash=None,
                gaps=[*gaps, "服务端核验时间缺少时区"],
            )
        elif not context.verified_at <= current <= context.valid_until:
            gaps.append("账户与费用核验已过期或时间无效")
        if request.cash_available_cny != context.cash_available_cny:
            gaps.append("可用现金与服务端资金证明不一致")
        if request.quote_at != context.quote_at:
            gaps.append("行情时间与服务端核验不一致")
        if request.quote_at is not None and (
            context.max_quote_age <= timedelta(0)
            or request.quote_at > current
            or current - request.quote_at > context.max_quote_age
        ):
            gaps.append("行情过期、时间在未来或未配置时效")
        rule = context.rules
        trading_date = current.astimezone(ZoneInfo("Asia/Shanghai")).date()
        if rule.effective_from > trading_date or (
            rule.effective_until is not None and rule.effective_until < trading_date
        ):
            gaps.append("交易规则尚未生效或已失效")
        if context.fees.verified_at > current or context.fees.verified_at < context.verified_at:
            gaps.append("费用证明未在本次核验窗口内确认")
        with localcontext() as tick_context:
            tick_context.prec = 500
            if (
                request.limit_price_cny is not None
                and request.limit_price_cny % rule.price_tick_cny
            ):
                gaps.append("限价不符合最小价格变动单位")
    if gaps:
        return ExecutionPreview(
            status="blocked",
            evidence_package_id=request.evidence_package_id,
            quantity=None,
            estimated_cost=None,
            remaining_cash=None,
            gaps=gaps,
        )
    assert context is not None
    assert request.cash_available_cny is not None and request.user_budget_cny is not None
    assert request.limit_price_cny is not None
    rule, fees = context.rules, context.fees
    price = request.limit_price_cny
    budget = min(request.cash_available_cny, request.user_budget_cny)
    # Bound arithmetic precision independently of the process/global Decimal context.
    values = (
        budget,
        request.cash_available_cny,
        request.limit_price_cny,
        fees.commission_rate,
        fees.minimum_commission_cny,
        fees.additional_rate,
        fees.additional_fixed_cny,
    )
    with localcontext() as arithmetic:
        arithmetic.prec = max(
            50,
            sum(len(v.as_tuple().digits) + abs(int(v.as_tuple().exponent)) for v in values)
            + len(str(rule.max_quantity))
            + 10,
        )

        def cost(quantity: int) -> Decimal:
            amount = price * quantity
            total = (
                amount
                + max(amount * fees.commission_rate, fees.minimum_commission_cny)
                + amount * fees.additional_rate
                + fees.additional_fixed_cny
            )
            return total.quantize(Decimal("0.01"), rounding=ROUND_CEILING)

        low, high = 0, (rule.max_quantity - rule.min_quantity) // rule.quantity_step
        best: int | None = None
        while low <= high:
            middle = (low + high) // 2
            quantity = rule.min_quantity + middle * rule.quantity_step
            if cost(quantity) <= budget:
                best = quantity
                low = middle + 1
            else:
                high = middle - 1
        if best is None:
            return ExecutionPreview(
                status="blocked",
                evidence_package_id=request.evidence_package_id,
                quantity=None,
                estimated_cost=None,
                remaining_cash=None,
                gaps=["现金或预算不足以覆盖最低申报数量及完整费用"],
            )
        total = cost(best)
        return ExecutionPreview(
            status="ready",
            evidence_package_id=request.evidence_package_id,
            quantity=best,
            estimated_cost=total,
            remaining_cash=request.cash_available_cny - total,
            gaps=[],
        )
