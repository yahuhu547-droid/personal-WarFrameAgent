from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Any

from .relic_value import analyze_relic_value
from .relics import RelicDrop, RelicInfo


_TIER_FROM_FISSURE = {
    "VoidT1": "Lith",
    "VoidT2": "Meso",
    "VoidT3": "Neo",
    "VoidT4": "Axi",
    "VoidT5": "Requiem",
    "Lith": "Lith",
    "Meso": "Meso",
    "Neo": "Neo",
    "Axi": "Axi",
    "Requiem": "Requiem",
}


@dataclass(frozen=True)
class ActiveFissureSummary:
    node: str
    mission: str
    tier: str
    tier_display: str = ""
    hard: bool = False
    expiry: str = ""


@dataclass(frozen=True)
class FarmingRoute:
    relic_name: str
    tier: str
    target_part: str
    market_id: str
    rarity: str
    drop_rate: float
    is_vaulted: bool
    sources: list[str] = field(default_factory=list)
    active_fissures: list[ActiveFissureSummary] = field(default_factory=list)
    expected_platinum: float | None = None
    expected_ducats: float | None = None
    score: float = 0.0
    recommendation: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FarmingRouteReport:
    target: str
    query_type: str
    routes: list[FarmingRoute]
    summary: str
    warnings: list[str] = field(default_factory=list)


def _fissure_tier(fissure: Any) -> str:
    raw_tier = str(getattr(fissure, "tier", "") or "")
    if raw_tier in _TIER_FROM_FISSURE:
        return _TIER_FROM_FISSURE[raw_tier]
    tier_display = str(getattr(fissure, "tier_display", "") or "")
    for tier in ("Lith", "Meso", "Neo", "Axi", "Requiem"):
        if tier in tier_display:
            return tier
    return raw_tier


def _summarize_fissure(fissure: Any) -> ActiveFissureSummary:
    return ActiveFissureSummary(
        node=str(getattr(fissure, "node_display", "") or getattr(fissure, "node", "")),
        mission=str(getattr(fissure, "mission_display", "") or getattr(fissure, "mission_type", "")),
        tier=_fissure_tier(fissure),
        tier_display=str(getattr(fissure, "tier_display", "") or ""),
        hard=bool(getattr(fissure, "hard", False)),
        expiry=str(getattr(fissure, "expiry", "") or ""),
    )


def _matching_fissures(tier: str, fissures: Iterable[Any]) -> list[ActiveFissureSummary]:
    return [_summarize_fissure(f) for f in fissures if _fissure_tier(f) == tier]


def _safe_sources(game_data: Any, relic_name: str) -> list[str]:
    getter = getattr(game_data, "get_relic_sources", None)
    if not callable(getter):
        return []
    try:
        sources = getter(relic_name) or []
    except Exception:
        return []
    return [str(source) for source in sources if str(source).strip()]


def _is_vaulted(game_data: Any, relic: RelicInfo) -> bool:
    getter = getattr(game_data, "is_vaulted", None)
    if callable(getter):
        try:
            return bool(getter(relic.name))
        except Exception:
            pass
    return bool(relic.is_vaulted)


def _score_route(drop_rate: float, is_vaulted: bool, source_count: int, fissure_count: int, expected_platinum: float | None) -> float:
    score = drop_rate * 100.0
    if not is_vaulted:
        score += 25.0
    else:
        score -= 20.0
    score += min(source_count, 5) * 4.0
    score += min(fissure_count, 3) * 10.0
    if expected_platinum is not None:
        score += min(expected_platinum, 50.0) * 0.2
    return round(score, 1)


def _route_recommendation(route: FarmingRoute) -> str:
    if route.active_fissures and not route.is_vaulted:
        return "优先刷取并趁当前同纪元裂缝开启"
    if route.is_vaulted:
        return "遗物可能已入库，优先确认库存或等待返场"
    if route.sources:
        return "可按来源刷遗物，再选择同纪元裂缝开启"
    return "来源数据不足，先确认遗物来源"


def _route_from_drop(
    drop: RelicDrop,
    relic: RelicInfo,
    game_data: Any,
    fissures: Iterable[Any],
    order_fetcher: Callable[[str], list[dict]] | None,
) -> FarmingRoute:
    sources = _safe_sources(game_data, relic.name)
    active_fissures = _matching_fissures(relic.tier, fissures)
    vaulted = _is_vaulted(game_data, relic)
    expected_platinum = None
    expected_ducats = None
    if order_fetcher is not None:
        try:
            value_report = analyze_relic_value(relic, order_fetcher, game_data)
            expected_platinum = value_report.expected_platinum
            expected_ducats = value_report.expected_ducats
        except Exception:
            expected_platinum = None
            expected_ducats = None
    warnings = []
    if vaulted:
        warnings.append("遗物可能已入库")
    if not sources:
        warnings.append("缺少可靠来源数据")
    if not active_fissures:
        warnings.append("当前没有匹配纪元裂缝")
    score = _score_route(drop.drop_rate, vaulted, len(sources), len(active_fissures), expected_platinum)
    route = FarmingRoute(
        relic_name=relic.name,
        tier=relic.tier,
        target_part=drop.part_name,
        market_id=drop.market_id,
        rarity=drop.rarity,
        drop_rate=drop.drop_rate,
        is_vaulted=vaulted,
        sources=sources,
        active_fissures=active_fissures,
        expected_platinum=expected_platinum,
        expected_ducats=expected_ducats,
        score=score,
        warnings=warnings,
    )
    return FarmingRoute(**{**route.__dict__, "recommendation": _route_recommendation(route)})


def analyze_farming_route(
    target: str,
    relic_db: Any,
    game_data: Any,
    fissures: Iterable[Any] | None = None,
    order_fetcher: Callable[[str], list[dict]] | None = None,
) -> FarmingRouteReport:
    query = str(target or "").strip()
    if not query:
        return FarmingRouteReport(target="", query_type="unknown", routes=[], summary="请提供 Prime 部件或遗物名称。", warnings=["缺少查询目标"])
    if hasattr(relic_db, "load"):
        relic_db.load()
    fissure_list = list(fissures or [])
    routes: list[FarmingRoute] = []
    query_type = "part"

    relic = relic_db.find_by_relic(query) if hasattr(relic_db, "find_by_relic") else None
    if relic:
        query_type = "relic"
        for drop in relic.drops:
            routes.append(_route_from_drop(drop, relic, game_data, fissure_list, order_fetcher))
    else:
        drops = relic_db.find_by_part(query) if hasattr(relic_db, "find_by_part") else []
        for drop in drops:
            relic_info = relic_db.find_by_relic(drop.relic_name) if hasattr(relic_db, "find_by_relic") else None
            if relic_info is None:
                relic_info = RelicInfo(name=drop.relic_name, tier=drop.relic_tier, is_vaulted=False, drops=[drop])
            routes.append(_route_from_drop(drop, relic_info, game_data, fissure_list, order_fetcher))

    routes.sort(key=lambda route: (route.score, route.drop_rate, not route.is_vaulted), reverse=True)
    if routes:
        summary = f"找到 {len(routes)} 条刷取路线，优先推荐 {routes[0].relic_name}。"
        warnings = []
    else:
        summary = "未找到相关遗物或部件掉落路线。"
        warnings = ["未匹配到遗物数据"]
    return FarmingRouteReport(target=query, query_type=query_type, routes=routes, summary=summary, warnings=warnings)


def format_farming_route_for_display(report: FarmingRouteReport, limit: int = 5) -> str:
    lines = [f"刷取路线：{report.target}", report.summary]
    if report.warnings:
        lines.append("提示：" + "；".join(report.warnings))
    for index, route in enumerate(report.routes[:limit], 1):
        vault_text = "已入库" if route.is_vaulted else "未入库/可用"
        lines.append(
            f"{index}. {route.relic_name} [{route.tier}] → {route.target_part} "
            f"掉率 {route.drop_rate * 100:.2f}% · 分数 {route.score} · {vault_text}"
        )
        if route.expected_platinum is not None or route.expected_ducats is not None:
            lines.append(f"   期望：{route.expected_platinum or 0}p / {route.expected_ducats or 0} 杜卡德")
        if route.sources:
            lines.append("   来源：" + "；".join(route.sources[:3]))
        if route.active_fissures:
            fissure_text = "；".join(f"{f.node} {f.mission}" for f in route.active_fissures[:3])
            lines.append("   当前裂缝：" + fissure_text)
        lines.append(f"   建议：{route.recommendation}")
        if route.warnings:
            lines.append("   注意：" + "；".join(route.warnings))
    return "\n".join(lines)


def format_farming_route_for_model(report: FarmingRouteReport, limit: int = 5) -> str:
    lines = [
        "tool=farming_route",
        f"target={report.target}",
        f"query_type={report.query_type}",
        f"route_count={len(report.routes)}",
        f"summary={report.summary}",
    ]
    for route in report.routes[:limit]:
        lines.append(
            "route "
            f"relic={route.relic_name} tier={route.tier} market_id={route.market_id} "
            f"drop_rate={route.drop_rate:.4f} vaulted={route.is_vaulted} "
            f"score={route.score} source_count={len(route.sources)} fissure_count={len(route.active_fissures)} "
            f"expected_platinum={route.expected_platinum} expected_ducats={route.expected_ducats}"
        )
    return "\n".join(lines)


def report_to_api(report: FarmingRouteReport) -> dict[str, Any]:
    return {
        "target": report.target,
        "queryType": report.query_type,
        "summary": report.summary,
        "warnings": report.warnings,
        "routes": [
            {
                "relicName": route.relic_name,
                "tier": route.tier,
                "targetPart": route.target_part,
                "marketId": route.market_id,
                "rarity": route.rarity,
                "dropRate": route.drop_rate,
                "isVaulted": route.is_vaulted,
                "sources": route.sources,
                "activeFissures": [f.__dict__ for f in route.active_fissures],
                "expectedPlatinum": route.expected_platinum,
                "expectedDucats": route.expected_ducats,
                "score": route.score,
                "recommendation": route.recommendation,
                "warnings": route.warnings,
            }
            for route in report.routes
        ],
    }
