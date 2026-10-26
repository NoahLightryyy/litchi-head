import pytest

from backend.related_keywords import extract_keywords


def terms(kind, code, name, **kwargs):
    return {item.term: item.origin for item in extract_keywords(kind, code, name, **kwargs)}


def test_etf_theme_removes_manager_suffix_and_expands_without_code_mapping():
    result = terms("etf", "560780", "半导体设备ETF广发")
    assert result["560780"] == "code"
    assert result["半导体设备ETF广发"] == "name"
    assert result["半导体设备"] == "name"
    assert result["集成电路"] == result["芯片"] == "expanded"
    assert "半导体" in result
    assert "广发" not in result and "设备" not in result and "银行" not in result
    other = terms("etf", "999999", "半导体设备ETF另一家管理人")
    assert "半导体设备" in other and "芯片" in other


def test_etf_known_prefix_manager_and_broad_index_name():
    result = terms("etf", "510300", "华夏沪深300ETF")
    assert "沪深300" in result
    assert "华夏" not in result and "人工智能" not in result and "半导体" not in result


def test_stock_exact_name_and_business_derive_theme_not_manager_or_code_guess():
    result = terms("stock", "688012", "中微公司", business="从事刻蚀和MOCVD设备的研发生产")
    assert result["中微公司"] == "name" and result["688012"] == "code"
    assert result["刻蚀"] == result["MOCVD"] == "business"
    assert result["半导体"] == result["集成电路"] == "expanded"
    assert terms("stock", "688012", "中微公司") == {"688012": "code", "中微公司": "name"}


@pytest.mark.parametrize(("name", "related", "unrelated"), [
    ("医药ETF", "药品", "半导体"),
    ("银行ETF", "信贷", "人工智能"),
    ("白酒ETF", "酒类", "芯片"),
    ("新能源车ETF", "动力电池", "疫苗"),
    ("光伏ETF", "太阳能", "信贷"),
    ("国防军工ETF", "军工", "旅游"),
    ("黄金ETF", "贵金属", "医药"),
])
def test_common_sector_topics_stay_relevant(name, related, unrelated):
    result = terms("etf", "999999", name)
    assert related in result and unrelated not in result


def test_generic_descriptions_do_not_fan_out_to_every_industry():
    result = terms("stock", "600001", "某某科技", business="从事设备制造及销售业务")
    assert result == {"600001": "code", "某某科技": "name"}


def test_numeric_placeholder_name_does_not_create_a_theme():
    assert terms("stock", "600001", "600001") == {"600001": "code"}
    assert terms("etf", "560780", "ETF") == {"560780": "code"}


def test_ascii_acronyms_obey_boundaries_but_work_next_to_chinese():
    unrelated = terms("stock", "600001", "TRAIN MEDIA", business="chair manufacturing")
    assert "AI" not in unrelated and "EDA" not in unrelated and "人工智能" not in unrelated
    relevant = terms("sector", "BK1234", "AI芯片", business="支持5G通信和EDA开发")
    assert relevant["AI"] == "name" and relevant["EDA"] == "business"
    assert "人工智能" in relevant and "5G" in relevant


def test_user_query_replaces_automatic_themes_and_preserves_user_terms():
    result = terms("etf", "560780", "半导体设备ETF广发", query=" 出口管制，设备补贴 出口管制 ")
    assert result == {"出口管制": "user", "设备补贴": "user"}
    assert "芯片" not in result and "560780" not in result


def test_single_character_cjk_user_terms_are_meaningful_refinements():
    assert terms("etf", "560780", "半导体设备ETF广发", query="铜，锂 铜") == {
        "铜": "user", "锂": "user",
    }
    assert terms("stock", "600001", "铜") == {"600001": "code"}


@pytest.mark.parametrize("query", ["A", "a 1", "!!", "……。", "!!! ,，； ??"])
def test_punctuation_and_single_character_ascii_are_not_keywords(query):
    assert terms("etf", "560780", "半导体设备ETF广发", query=query) == {}


def test_terms_are_bounded_deduplicated_and_whitespace_normalized():
    result = extract_keywords("stock", "600001", "  AI 公司  ", business=(
        "AI人工智能 半导体芯片 集成电路 光伏 电网 核电 医药 创新药 银行 白酒 物流 黄金 软件"
    ))
    assert len(result) == 12
    assert len({item.term.casefold() for item in result}) == len(result)
    assert "AI 公司" in {item.term for item in result}
    assert all(2 <= len(item.term) <= 80 for item in result)
    assert terms("sector", "BK1234", "行业", query="A " + "政" * 100) == {"政" * 80: "user"}
