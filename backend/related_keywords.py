"""Deterministic retrieval terms; topic expansion never implies investment exposure."""

from __future__ import annotations

import re
from typing import Literal

from backend.related_research_contract import RelatedKeyword, SubjectKind

# Specific industry terms may suggest nearby search vocabulary. Generic words such
# as “设备”“科技”“制造” are deliberately absent: they do not identify a sector.
_TOPICS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("半导体设备", "半导体", "集成电路", "芯片", "晶圆", "光刻", "刻蚀", "MOCVD", "EDA"),
     ("半导体", "集成电路", "芯片")),
    (("人工智能", "生成式人工智能", "大模型", "智能体", "AIGC", "AI"),
     ("人工智能", "大模型", "智能体")),
    (("算力", "数据中心", "智算", "GPU", "服务器"), ("算力", "数据中心")),
    (("机器人", "工业自动化", "人形机器人", "工业母机", "数控机床"),
     ("机器人", "工业自动化")),
    (("光伏", "太阳能", "光伏组件", "硅片"), ("光伏", "太阳能")),
    (("风电", "风力发电", "海上风电"), ("风电", "风力发电")),
    (("锂电", "锂离子电池", "动力电池", "储能", "固态电池"), ("锂电", "储能", "动力电池")),
    (("新能源汽车", "新能源车", "电动汽车", "充电桩"),
     ("新能源汽车", "动力电池", "充电桩")),
    (("电网", "特高压", "输配电", "电力设备"), ("电网", "特高压")),
    (("电力", "发电", "水电", "火电", "核电"), ("电力", "发电")),
    (("医药", "制药", "生物医药", "创新药", "原料药", "疫苗"),
     ("医药", "创新药", "药品")),
    (("医疗器械", "医疗设备", "体外诊断", "IVD"), ("医疗器械", "医疗设备")),
    (("白酒", "酿酒"), ("白酒", "酒类")),
    (("食品", "饮料", "乳业", "乳制品"), ("食品", "消费")),
    (("银行", "商业银行"), ("银行", "信贷")),
    (("证券", "券商", "资本市场"), ("证券", "资本市场")),
    (("保险", "寿险", "财险"), ("保险", "保险资金")),
    (("房地产", "地产", "住宅开发"), ("房地产", "住房")),
    (("建筑", "基建", "基础设施"), ("建筑", "基础设施")),
    (("军工", "国防", "军用"), ("军工", "国防")),
    (("航空", "航天", "卫星", "低空经济", "无人机"), ("航空航天", "低空经济")),
    (("通信", "光模块", "5G", "6G", "电信"), ("通信", "光模块")),
    (("软件", "信息技术", "网络安全", "信创", "云计算"), ("软件", "信息技术")),
    (("黄金", "贵金属"), ("黄金", "贵金属")),
    (("有色金属", "铜业", "铝业", "稀土"), ("有色金属", "金属")),
    (("煤炭", "煤矿", "焦煤"), ("煤炭", "能源")),
    (("石油", "天然气", "油气", "炼化"), ("石油", "天然气")),
    (("化工", "化学材料", "化肥"), ("化工", "化学材料")),
    (("农业", "种业", "养殖", "饲料", "畜牧"), ("农业", "粮食")),
    (("物流", "快递", "航运", "港口"), ("物流", "运输")),
    (("游戏", "传媒", "影视", "文化产业"), ("传媒", "文化产业")),
    (("旅游", "酒店", "免税"), ("旅游", "消费")),
)
_MANAGERS = (
    "易方达", "国泰海通", "国联安", "华泰柏瑞", "工银瑞信", "交银施罗德", "中银",
    "华夏", "广发", "南方", "华安", "嘉实", "博时", "富国", "天弘", "招商", "鹏华",
    "汇添富", "景顺长城", "银华", "国泰", "平安", "建信", "兴业", "华宝", "海富通",
)
_GENERIC = {"ETF", "基金", "指数", "证券投资基金", "股票", "行业", "概念", "设备", "科技"}


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _contains(text: str, term: str) -> bool:
    # ASCII acronyms must not match inside company names such as “TRAIN” or
    # “MEDIA”. Chinese neighbors are valid, for example “AI芯片” and “5G通信”.
    if re.fullmatch(r"[A-Za-z0-9]+", term):
        return bool(re.search(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])",
                              text, re.IGNORECASE))
    return term.casefold() in text.casefold()


def _etf_theme(name: str) -> str:
    # The quoted market name often places the manager after ETF. Truncating that
    # suffix handles new managers too; prefixes are removed only when known.
    parts = re.split(r"ETF", name, maxsplit=1, flags=re.IGNORECASE)
    theme = parts[0].strip() or (parts[1].strip() if len(parts) > 1 else "")
    for manager in _MANAGERS:
        if theme.startswith(manager):
            theme = theme[len(manager):].lstrip()
        if theme.endswith(manager):
            theme = theme[:-len(manager)].rstrip()
    theme = re.sub(r"(?:交易型开放式)?指数(?:证券投资)?基金.*$", "", theme)
    theme = re.sub(r"(?:联接|增强|发起式)[ABC]?\b.*$", "", theme)
    return theme.strip(" ·-（）()")


def extract_keywords(
    kind: SubjectKind, code: str, name: str, business: str = "", query: str = ""
) -> list[RelatedKeyword]:
    """Extract up to 12 display-search terms without LLM calls or code lists.

    An explicit query replaces automatic terms, so a user refinement cannot be
    overwhelmed by unrelated articles matching the original company or theme.
    Origins describe how a term was found, not a verified issuer-policy link.
    """
    result: list[RelatedKeyword] = []
    seen: set[str] = set()

    def add(term: str, origin: Literal["name", "business", "expanded", "user", "code"]) -> None:
        term = _clean(term)[:80]
        key = term.casefold()
        single_cjk_query = origin == "user" and bool(re.fullmatch(r"[\u3400-\u9fff]", term))
        searchable = bool(re.search(r"[A-Za-z0-9\u3400-\u9fff]", term))
        if (searchable and (len(term) >= 2 or single_cjk_query)
                and key not in seen and len(result) < 12):
            result.append(RelatedKeyword(term=term, origin=origin))
            seen.add(key)

    if query.strip():
        for term in re.split(r"[\s,，;；、]+", query.strip()):
            add(term, "user")
        return result

    code, name = _clean(code), _clean(name)
    add(code, "code")
    if name and not name.isdecimal() and name.upper() not in _GENERIC:
        add(name, "name")
    topic_name = _etf_theme(name) if kind == "etf" else name
    if kind == "etf" and topic_name and not topic_name.isdecimal():
        if topic_name.upper() not in _GENERIC:
            add(topic_name, "name")

    # Match all directly observed vocabulary first. Expansions come afterwards
    # so a long business description keeps its own specific terms within the cap.
    matched: list[tuple[str, ...]] = []
    for terms, expansions in _TOPICS:
        relevant = False
        for term in terms:
            if _contains(topic_name, term):
                add(term, "name")
                relevant = True
            elif _contains(business, term):
                add(term, "business")
                relevant = True
        if relevant:
            matched.append(expansions)
    for expansions in matched:
        for term in expansions:
            add(term, "expanded")
    return result
