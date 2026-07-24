"""PD-004a 行业覆盖验证 —— 实锤 API 验证

从 31 个一级行业中各选代表股票，调用东方财富 API 获取其行业分类，
验证 normalize_industry() 是否能正确映射。

用法：
    python scripts/verify_industry_coverage.py
"""

import sys
import time
from pathlib import Path

# Windows GBK 编码兼容
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.upper() == "GBK":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

# 确保能导入 src/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.indicators.registry import (
    SHENWAN_SECTORS,
    normalize_industry,
)

# ── 各行业代表股票（每个行业 2-3 只） ─────────────────────────────

SAMPLE_STOCKS: dict[str, list[str]] = {
    "银行": ["000001", "600036"],              # 平安银行, 招商银行
    "非银金融": ["601318", "600030"],          # 中国平安, 中信证券
    "煤炭": ["601088", "600188"],              # 中国神华, 兖矿能源
    "石油石化": ["600028", "601857"],          # 中国石化, 中国石油
    "有色金属": ["601899", "000630"],          # 紫金矿业, 铜陵有色
    "钢铁": ["600019", "000708"],              # 宝钢股份, 中信特钢
    "基础化工": ["600309", "002709"],          # 万华化学, 天赐材料
    "食品饮料": ["600519", "000858"],          # 贵州茅台, 五粮液
    "医药生物": ["600276", "300015"],          # 恒瑞医药, 爱尔眼科
    "房地产": ["000002", "600048"],            # 万科A, 保利发展
    "电子": ["000725", "002475"],              # 京东方A, 立讯精密
    "计算机": ["002415", "000977"],            # 海康威视, 浪潮信息
    "传媒": ["300413", "002624"],              # 芒果超媒, 完美世界
    "通信": ["600941", "000063"],              # 中国移动, 中兴通讯
    "汽车": ["600104", "000625"],              # 上汽集团, 长安汽车
    "电力设备": ["300750", "601012"],          # 宁德时代, 隆基绿能
    "机械设备": ["600150", "000338"],          # 中国船舶, 潍柴动力
    "国防军工": ["600760", "600893"],          # 中航沈飞, 航发动力
    "建筑装饰": ["601668", "601390"],          # 中国建筑, 中国中铁
    "建筑材料": ["600585", "000786"],          # 海螺水泥, 北新建材
    "交通运输": ["601919", "601006"],          # 中远海控, 大秦铁路
    "商贸零售": ["601933", "600827"],          # 永辉超市, 百联股份
    "农林牧渔": ["000876", "002714"],          # 新希望, 牧原股份
    "家用电器": ["000651", "002032"],          # 格力电器, 苏泊尔
    "纺织服饰": ["002832", "600398"],          # 比音勒芬, 海澜之家
    "轻工制造": ["002572", "603833"],          # 索菲亚, 欧派家居
    "社会服务": ["601888", "300144"],          # 中国中免, 宋城演艺
    "公用事业": ["600900", "600886"],          # 长江电力, 国投电力
    "环保": ["600323", "300070"],              # 瀚蓝环境, 碧水源
    "美容护理": ["300740", "600315"],          # 水羊股份, 上海家化
    "综合": ["600620", "600805"],              # 天宸股份, 悦达投资
}


def verify_coverage():
    """调用东方财富 API 验证行业映射覆盖率"""
    try:
        import akshare as ak  # noqa: PLC0415
    except ImportError:
        print("❌ 需要安装 akshare: pip install akshare")
        return False

    total = 0
    mapped = 0
    unmapped: list[tuple[str, str, str]] = []  # (code, raw_industry, expected_sector)
    errors: list[tuple[str, str]] = []           # (code, error_msg)

    print(f"\n{'='*60}")
    print("PD-004a 行业覆盖验证")
    print(f"样本: {sum(len(v) for v in SAMPLE_STOCKS.values())} 只股票")
    print(f"{'='*60}\n")

    for sector, codes in SAMPLE_STOCKS.items():
        print(f"\n📂 {sector}:")
        for code in codes:
            total += 1
            try:
                info = ak.stock_individual_info_em(code)
                raw_industry = str(info[info["item"] == "行业"].iloc[0]["value"])

                normalized = normalize_industry(raw_industry)

                is_level1 = raw_industry in SHENWAN_SECTORS or raw_industry == sector
                if normalized == raw_industry and not is_level1:
                    # 没有映射到一级行业
                    unmapped.append((code, raw_industry, sector))
                    print(f"  ⚠️ {code}: {raw_industry} → ❌ 未映射")
                elif normalized != sector:
                    # 映射到了不同的行业
                    print(f"  ⚠️ {code}: {raw_industry} → {normalized} (预期 {sector})")
                    unmapped.append((code, raw_industry, sector))
                else:
                    mapped += 1
                    print(f"  ✅ {code}: {raw_industry} → {normalized}")

                time.sleep(0.3)  # API 限流
            except Exception as e:
                errors.append((code, str(e)[:80]))
                print(f"  ❌ {code}: API 调用失败 — {e}")

    # ── 汇总 ──
    print(f"\n{'='*60}")
    print("验证汇总:")
    print(f"  总样本: {total}")
    print(f"  成功映射: {mapped}/{total} ({mapped/total*100:.1f}%)")
    if unmapped:
        print(f"\n  ⚠️ 未映射/映射偏差 ({len(unmapped)}):")
        for code, raw, expected in unmapped:
            print(f"    {code}: '{raw}' (预期 {expected})")
            print("      → 需要补充到 _INDUSTRY_NORMALIZE")
    if errors:
        print(f"\n  ❌ API 错误 ({len(errors)}):")
        for code, err in errors:
            print(f"    {code}: {err}")
    print(f"{'='*60}\n")

    return len(unmapped) == 0


if __name__ == "__main__":
    ok = verify_coverage()
    sys.exit(0 if ok else 1)
