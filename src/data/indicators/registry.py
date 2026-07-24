"""PD 动态指标体系 —— 注册表模型 + 31 行业关键指标定义

基于实锤 API 验证的东方财富行业分类（496 子板块 → 31 一级行业）。

数据来源：
- `ak.stock_board_industry_name_em()` → 496 个行业板块（2026-07-24 验证）
- `ak.stock_individual_info_em('000001')` → f127="银行Ⅱ"（2026-07-24 验证）
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

# ── 产业链位置枚举 ──────────────────────────────────────────────────────


class IndustryChainPosition(str, Enum):
    """产业链位置

    基于行业归属判断公司在产业链中的生态位。
    A 股标准分析框架：上游（资源采掘）、中游（制造加工）、下游（品牌/渠道/服务）。
    """

    UPSTREAM = "upstream"        # 上游：资源采掘/原材料
    MIDSTREAM = "midstream"      # 中游：制造/加工/组装
    DOWNSTREAM = "downstream"    # 下游：品牌/渠道/服务/消费
    FINANCIAL = "financial"      # 金融行业（特殊，不适用产业链分析）
    OTHER = "other"              # 综合/未知


# ── 指标定义模型 ────────────────────────────────────────────────────────

_IndicatorCategory = Literal[
    "valuation",      # 估值比率（PE/PB/PS）
    "profitability",  # 盈利能力（ROE/ROA/毛利率/净利率）
    "growth",         # 增长能力（营收/利润增长率）
    "health",         # 财务健康（负债率/流动/速动比率）
    "per_share",      # 每股指标（EPS/每股净资产/每股经营现金流）
    "efficiency",     # 运营效率（存货/资产周转率）
    "scale",          # 规模（总资产/主营利润）
]


class IndicatorDef(BaseModel):
    """关键指标定义

    每个指标绑定到 FinancialMetrics 的字段，
    用于按行业动态选取 5-10 个最关键的指标。
    """

    id: str                                           # "pe", "roe"
    name: str                                         # "市盈率"
    description: str                                  # 一句话解读
    field: str                                        # FinancialMetrics 字段名
    category: _IndicatorCategory = "profitability"
    unit: str = ""                                    # "%" / "倍" / "次" / "元"
    normal_range_hint: str = ""                       # "10-20倍"
    higher_is_better: bool = True                     # 越大越好？
    priority: int = Field(default=5, ge=1, le=10)    # 优先级 1-10


# ── 全部指标定义 ────────────────────────────────────────────────────────

INDICATOR_DEFS: list[IndicatorDef] = [
    # ── 估值 ──
    IndicatorDef(id="pe", name="市盈率", description="股价/每股收益，衡量估值高低，越低越便宜",
                 field="pe", category="valuation", unit="倍", normal_range_hint="10-20倍",
                 higher_is_better=False, priority=9),
    IndicatorDef(id="pb", name="市净率", description="股价/每股净资产，衡量资产估值",
                 field="pb", category="valuation", unit="倍", normal_range_hint="1-3倍",
                 higher_is_better=False, priority=8),
    IndicatorDef(id="ps", name="市销率", description="总市值/主营收入，适合亏损公司的估值",
                 field="ps", category="valuation", unit="倍", normal_range_hint="1-5倍",
                 higher_is_better=False, priority=6),
    # ── 盈利能力 ──
    IndicatorDef(id="roe", name="净资产收益率", description="净利润/净资产，衡量股东回报效率",
                 field="roe", category="profitability", unit="%", normal_range_hint="10-20%",
                 priority=10),
    IndicatorDef(id="roa", name="总资产利润率", description="净利润/总资产，衡量资产利用效率",
                 field="roa", category="profitability", unit="%", normal_range_hint="5-10%",
                 priority=6),
    IndicatorDef(id="gross_margin", name="销售毛利率",
                 description="(营收-营业成本)/营收，衡量产品定价权和成本控制能力",
                 field="gross_margin", category="profitability", unit="%",
                 normal_range_hint="30-70%", priority=8),
    IndicatorDef(id="net_profit_margin", name="销售净利率",
                 description="净利润/营收，衡量最终盈利水平",
                 field="net_profit_margin", category="profitability", unit="%",
                 normal_range_hint="10-30%", priority=7),
    # ── 增长能力 ──
    IndicatorDef(id="revenue_growth", name="营业收入增长率",
                 description="营收同比增幅，衡量成长性",
                 field="revenue_growth", category="growth", unit="%",
                 normal_range_hint="10-30%", priority=9),
    IndicatorDef(id="net_profit_growth", name="净利润增长率",
                 description="净利润同比增幅，衡量盈利成长性",
                 field="net_profit_growth", category="growth", unit="%",
                 normal_range_hint="10-30%", priority=8),
    # ── 财务健康 ──
    IndicatorDef(id="debt_ratio", name="资产负债率",
                 description="总负债/总资产，衡量财务杠杆和偿债风险",
                 field="debt_ratio", category="health", unit="%",
                 normal_range_hint="30-60%", higher_is_better=False, priority=8),
    IndicatorDef(id="current_ratio", name="流动比率",
                 description="流动资产/流动负债，衡量短期偿债能力",
                 field="current_ratio", category="health", unit="倍",
                 normal_range_hint="1.5-3.0", priority=7),
    IndicatorDef(id="quick_ratio", name="速动比率",
                 description="(流动资产-存货)/流动负债，更严格的短期偿债能力",
                 field="quick_ratio", category="health", unit="倍",
                 normal_range_hint="1.0-1.5", priority=6),
    # ── 每股指标 ──
    IndicatorDef(id="eps", name="每股收益(EPS)",
                 description="净利润/总股本，每股能分多少利润，核心盈利指标",
                 field="eps", category="per_share", unit="元",
                 normal_range_hint=">0.5元", priority=9),
    IndicatorDef(id="book_value_per_share", name="每股净资产",
                 description="净资产/总股本，每股对应的资产价值",
                 field="book_value_per_share", category="per_share", unit="元",
                 normal_range_hint=">5元", priority=6),
    IndicatorDef(id="operating_cf_per_share", name="每股经营性现金流",
                 description="经营现金流/总股本，衡量现金创造能力",
                 field="operating_cf_per_share", category="per_share", unit="元",
                 normal_range_hint=">EPS", priority=7),
    # ── 运营效率 ──
    IndicatorDef(id="inventory_turnover", name="存货周转率",
                 description="营业成本/平均存货，衡量存货管理效率，越高周转越快",
                 field="inventory_turnover", category="efficiency", unit="次",
                 priority=7),
    IndicatorDef(id="asset_turnover", name="总资产周转率",
                 description="营收/总资产，衡量资产运营效率",
                 field="asset_turnover", category="efficiency", unit="次",
                 normal_range_hint=">0.5次", priority=6),
    # ── 规模 ──
    IndicatorDef(id="total_assets", name="总资产",
                 description="公司资产总规模，衡量体量",
                 field="total_assets", category="scale", unit="亿元",
                 priority=4),
    IndicatorDef(id="operating_revenue", name="主营业务收入",
                 description="公司主营业务产生的收入",
                 field="operating_revenue", category="scale", unit="亿元",
                 priority=5),
]

# id → IndicatorDef 快速查找
INDICATOR_DEFS_MAP: dict[str, IndicatorDef] = {d.id: d for d in INDICATOR_DEFS}


# ── 行业名称归一化映射 ─────────────────────────────────────────────────

# API 返回的行业名 → 一级行业名（基于实锤 API 数据验证）
# 覆盖东方财富全部 496 个子板块，映射到 31 个一级行业
_INDUSTRY_NORMALIZE: dict[str, str] = {
    # ── 银行 ──
    "银行": "银行", "银行Ⅱ": "银行",
    "股份制银行Ⅲ": "银行", "城商行Ⅲ": "银行",
    "国有大型银行Ⅲ": "银行", "农商行Ⅲ": "银行",
    # ── 非银金融 ──
    "非银金融": "非银金融",
    "证券Ⅱ": "非银金融", "证券Ⅲ": "非银金融",
    "保险Ⅱ": "非银金融", "保险Ⅲ": "非银金融",
    "多元金融": "非银金融",
    "期货": "非银金融", "信托": "非银金融",
    "金融控股": "非银金融", "金融信息服务": "非银金融",
    "资产管理": "非银金融", "租赁": "非银金融",
    # ── 煤炭 ──
    "煤炭": "煤炭",
    "煤炭开采": "煤炭",
    "焦炭Ⅱ": "煤炭", "焦炭Ⅲ": "煤炭",
    "动力煤": "煤炭", "焦煤": "煤炭",
    "煤化工": "煤炭",
    # ── 石油石化 ──
    "石油石化": "石油石化",
    "炼化及贸易": "石油石化",
    "油气开采Ⅱ": "石油石化", "油气开采Ⅲ": "石油石化",
    "油服工程": "石油石化",
    "油品石化贸易": "石油石化",
    "炼油化工": "石油石化",
    "其他石化": "石油石化",
    # ── 有色金属 ──
    "有色金属": "有色金属",
    "铜": "有色金属", "铝": "有色金属",
    "黄金": "有色金属", "铅锌": "有色金属",
    "稀土": "有色金属", "钨": "有色金属",
    "钴": "有色金属", "锂": "有色金属",
    "镍": "有色金属", "钼": "有色金属",
    "白银": "有色金属", "锡": "有色金属",
    "工业金属": "有色金属",
    "能源金属": "有色金属",
    "金属新材料": "有色金属",
    "小金属": "有色金属", "其他小金属": "有色金属",
    "贵金属": "有色金属",
    "磁性材料": "有色金属",
    "其他金属新材料": "有色金属",
    # ── 钢铁 ──
    "钢铁": "钢铁",
    "普钢": "钢铁", "特钢Ⅱ": "钢铁", "特钢Ⅲ": "钢铁",
    "冶钢原料": "钢铁", "冶钢辅料": "钢铁",
    "钢铁管材": "钢铁",
    "铁矿石": "钢铁",
    "板材": "钢铁", "长材": "钢铁",
    # ── 基础化工 ──
    "基础化工": "基础化工",
    "化学原料": "基础化工", "化学制品": "基础化工",
    "化学纤维": "基础化工",
    "农化制品": "基础化工",
    "塑料": "基础化工", "橡胶": "基础化工",
    "农药": "基础化工",
    "氮肥": "基础化工", "复合肥": "基础化工",
    "钾肥": "基础化工", "磷肥及磷化工": "基础化工",
    "有机硅": "基础化工", "纯碱": "基础化工",
    "氯碱": "基础化工", "钛白粉": "基础化工",
    "聚氨酯": "基础化工",
    "涂料": "基础化工", "涂料油墨": "基础化工",
    "改性塑料": "基础化工",
    "合成树脂": "基础化工",
    "膜材料": "基础化工",
    "炭黑": "基础化工",
    "其他塑料制品": "基础化工",
    "其他橡胶制品": "基础化工",
    "其他化学原料": "基础化工",
    "其他化学制品": "基础化工",
    "纺织化学制品": "基础化工",
    "食品及饲料添加剂": "基础化工",
    "氟化工": "基础化工",
    "胶黏剂及胶带": "基础化工",
    "民爆制品": "基础化工",
    "氨纶": "基础化工", "涤纶": "基础化工",
    "锦纶": "基础化工", "粘胶": "基础化工",
    "其他化学纤维": "基础化工",
    # ── 食品饮料 ──
    "食品饮料": "食品饮料",
    "白酒Ⅱ": "食品饮料", "白酒Ⅲ": "食品饮料",
    "非白酒": "食品饮料",
    "啤酒": "食品饮料",
    "食品加工": "食品饮料",
    "调味发酵品Ⅱ": "食品饮料", "调味发酵品Ⅲ": "食品饮料",
    "乳品": "食品饮料",
    "软饮料": "食品饮料",
    "肉制品": "食品饮料",
    "休闲食品": "食品饮料",
    "保健品": "食品饮料",
    "预加工食品": "食品饮料",
    "烘焙食品": "食品饮料",
    "零食": "食品饮料", "熟食": "食品饮料",
    "其他酒类": "食品饮料",
    "饮料乳品": "食品饮料",
    # ── 医药生物 ──
    "医药生物": "医药生物",
    "中药Ⅱ": "医药生物", "中药Ⅲ": "医药生物",
    "化学制药": "医药生物",
    "化学制剂": "医药生物", "原料药": "医药生物",
    "生物制品": "医药生物",
    "其他生物制品": "医药生物",
    "血液制品": "医药生物", "疫苗": "医药生物",
    "医疗器械": "医药生物",
    "医疗耗材": "医药生物", "医疗设备": "医药生物",
    "医疗研发外包": "医药生物",
    "医疗服务": "医药生物",
    "医院": "医药生物",
    "诊断服务": "医药生物",
    "体外诊断": "医药生物",
    "医药商业": "医药生物",
    "医药流通": "医药生物",
    "线下药店": "医药生物",
    "医美耗材": "医药生物",
    "医美服务": "医药生物",
    "其他医疗服务": "医药生物",
    # ── 房地产 ──
    "房地产": "房地产",
    "房地产开发": "房地产",
    "房地产服务": "房地产",
    "住宅开发": "房地产",
    "商业地产": "房地产",
    "产业地产": "房地产",
    "房地产综合服务": "房地产",
    "物业管理": "房地产",
    # ── 电子 ──
    "电子": "电子",
    "半导体": "电子",
    "半导体材料": "电子", "半导体设备": "电子",
    "分立器件": "电子",
    "集成电路封测": "电子",
    "集成电路制造": "电子",
    "模拟芯片设计": "电子", "数字芯片设计": "电子",
    "电子化学品Ⅱ": "电子", "电子化学品Ⅲ": "电子",
    "消费电子": "电子",
    "消费电子零部件及组装": "电子",
    "品牌消费电子": "电子",
    "光学光电子": "电子",
    "光学元件": "电子",
    "LED": "电子",
    "面板": "电子",
    "元件": "电子",
    "印制电路板": "电子",
    "其他电子Ⅱ": "电子", "其他电子Ⅲ": "电子",
    # ── 计算机 ──
    "计算机": "计算机",
    "计算机设备": "计算机",
    "IT服务Ⅱ": "计算机", "IT服务Ⅲ": "计算机",
    "软件开发": "计算机",
    "安防设备": "计算机",
    "其他计算机设备": "计算机",
    "垂直应用软件": "计算机",
    "横向通用软件": "计算机",
    # ── 传媒 ──
    "传媒": "传媒",
    "游戏Ⅱ": "传媒", "游戏Ⅲ": "传媒",
    "影视院线": "传媒",
    "影视动漫制作": "传媒", "院线": "传媒",
    "广告营销": "传媒",
    "营销代理": "传媒", "广告媒体": "传媒",
    "数字媒体": "传媒",
    "视频媒体": "传媒", "图片媒体": "传媒",
    "文字媒体": "传媒",
    "门户网站": "传媒",
    "其他数字媒体": "传媒",
    "出版": "传媒",
    "大众出版": "传媒", "教育出版": "传媒",
    "电视广播Ⅱ": "传媒", "电视广播Ⅲ": "传媒",
    # ── 通信 ──
    "通信": "通信",
    "通信服务": "通信",
    "通信设备": "通信",
    "通信工程及服务": "通信",
    "通信应用增值服务": "通信",
    "通信网络设备及器件": "通信",
    "通信线缆及配套": "通信",
    "通信终端及配件": "通信",
    "其他通信设备": "通信",
    "电信运营商": "通信",
    # ── 汽车 ──
    "汽车": "汽车",
    "汽车零部件": "汽车",
    "乘用车": "汽车",
    "商用车": "汽车",
    "电动乘用车": "汽车",
    "综合乘用车": "汽车",
    "商用载货车": "汽车", "商用载客车": "汽车",
    "摩托车": "汽车", "摩托车及其他": "汽车",
    "汽车服务": "汽车",
    "汽车经销商": "汽车",
    "汽车综合服务": "汽车",
    "车身附件及饰件": "汽车",
    "底盘与发动机系统": "汽车",
    "轮胎轮毂": "汽车",
    "其他汽车零部件": "汽车",
    "汽车电子电气系统": "汽车",
    "其他运输设备": "汽车",
    # ── 电力设备 ──
    "电力设备": "电力设备",
    "电网设备": "电力设备",
    "配电设备": "电力设备",
    "输变电设备": "电力设备",
    "线缆部件及其他": "电力设备",
    "电机Ⅱ": "电力设备", "电机Ⅲ": "电力设备",
    "电工仪器仪表": "电力设备",
    "电网自动化设备": "电力设备",
    "光伏设备": "电力设备",
    "光伏电池组件": "电力设备",
    "光伏辅材": "电力设备",
    "光伏加工设备": "电力设备",
    "光伏主材": "电力设备",
    "硅料硅片": "电力设备",
    "风电设备": "电力设备",
    "风电零部件": "电力设备", "风电整机": "电力设备",
    "电池": "电力设备",
    "电池化学品": "电力设备",
    "锂电池": "电力设备",
    "锂电专用设备": "电力设备",
    "燃料电池": "电力设备",
    "蓄电池及其他电池": "电力设备",
    "逆变器": "电力设备",
    "其他电源设备Ⅱ": "电力设备", "其他电源设备Ⅲ": "电力设备",
    "综合电力设备商": "电力设备",
    "火电设备": "电力设备",
    # ── 机械设备 ──
    "机械设备": "机械设备",
    "通用设备": "机械设备",
    "专用设备": "机械设备",
    "自动化设备": "机械设备",
    "工程机械": "机械设备",
    "工程机械器件": "机械设备", "工程机械整机": "机械设备",
    "机床工具": "机械设备",
    "机器人": "机械设备",
    "激光设备": "机械设备",
    "工控设备": "机械设备",
    "其他自动化设备": "机械设备",
    "其他通用设备": "机械设备",
    "其他专用设备": "机械设备",
    "能源及重型设备": "机械设备",
    "农用机械": "机械设备",
    "纺织服装设备": "机械设备",
    "印刷包装机械": "机械设备",
    "制冷空调设备": "机械设备",
    "楼宇设备": "机械设备",
    "仪器仪表": "机械设备",
    "金属制品": "机械设备",
    "磨具磨料": "机械设备",
    # ── 国防军工 ──
    "国防军工": "国防军工",
    "地面兵装Ⅱ": "国防军工", "地面兵装Ⅲ": "国防军工",
    "航海装备Ⅱ": "国防军工", "航海装备Ⅲ": "国防军工",
    "航空装备Ⅱ": "国防军工", "航空装备Ⅲ": "国防军工",
    "航天装备Ⅱ": "国防军工", "航天装备Ⅲ": "国防军工",
    "军工电子Ⅱ": "国防军工", "军工电子Ⅲ": "国防军工",
    # ── 建筑装饰 ──
    "建筑装饰": "建筑装饰",
    "房屋建设Ⅱ": "建筑装饰", "房屋建设Ⅲ": "建筑装饰",
    "基础建设": "建筑装饰",
    "基建市政工程": "建筑装饰",
    "装修装饰Ⅱ": "建筑装饰", "装修装饰Ⅲ": "建筑装饰",
    "钢结构": "建筑装饰",
    "园林工程": "建筑装饰",
    "国际工程": "建筑装饰",
    "化学工程": "建筑装饰",
    "其他专业工程": "建筑装饰",
    "工程咨询服务Ⅱ": "建筑装饰", "工程咨询服务Ⅲ": "建筑装饰",
    # ── 建筑材料 ──
    "建筑材料": "建筑材料",
    "水泥": "建筑材料",
    "水泥制造": "建筑材料",
    "水泥制品": "建筑材料",
    "玻璃玻纤": "建筑材料",
    "玻璃制造": "建筑材料",
    "玻纤制造": "建筑材料",
    "装修建材": "建筑材料",
    "耐火材料": "建筑材料",
    "防水材料": "建筑材料",
    "管材": "建筑材料",
    "其他建材": "建筑材料",
    "非金属材料Ⅱ": "建筑材料", "非金属材料Ⅲ": "建筑材料",
    # ── 交通运输 ──
    "交通运输": "交通运输",
    "航空机场": "交通运输",
    "航空运输": "交通运输", "机场": "交通运输",
    "铁路公路": "交通运输",
    "高速公路": "交通运输", "铁路运输": "交通运输",
    "航运港口": "交通运输",
    "港口": "交通运输", "航运": "交通运输",
    "物流": "交通运输",
    "仓储物流": "交通运输",
    "快递": "交通运输",
    "跨境物流": "交通运输",
    "公路货运": "交通运输",
    "公交": "交通运输",
    "原材料供应链服务": "交通运输",
    "端到端供应链服务": "交通运输",
    # ── 商贸零售 ──
    "商贸零售": "商贸零售",
    "一般零售": "商贸零售",
    "贸易Ⅱ": "商贸零售", "贸易Ⅲ": "商贸零售",
    "百货": "商贸零售", "超市": "商贸零售",
    "多业态零售": "商贸零售",
    "商业物业经营": "商贸零售",
    "跨境电商": "商贸零售",
    "电商服务": "商贸零售",
    "互联网电商": "商贸零售",
    "旅游零售Ⅱ": "商贸零售", "旅游零售Ⅲ": "商贸零售",
    "专业连锁Ⅱ": "商贸零售", "专业连锁Ⅲ": "商贸零售",
    # ── 农林牧渔 ──
    "农林牧渔": "农林牧渔",
    "种植业": "农林牧渔",
    "粮食种植": "农林牧渔",
    "其他种植业": "农林牧渔",
    "食用菌": "农林牧渔", "种子": "农林牧渔",
    "养殖业": "农林牧渔",
    "生猪养殖": "农林牧渔",
    "肉鸡养殖": "农林牧渔",
    "其他养殖": "农林牧渔",
    "水产养殖": "农林牧渔",
    "饲料": "农林牧渔",
    "畜禽饲料": "农林牧渔", "水产饲料": "农林牧渔",
    "农产品加工": "农林牧渔",
    "果蔬加工": "农林牧渔",
    "粮油加工": "农林牧渔",
    "其他农产品加工": "农林牧渔",
    "渔业": "农林牧渔",
    "海洋捕捞": "农林牧渔",
    "林业Ⅱ": "农林牧渔", "林业Ⅲ": "农林牧渔",
    "农业综合Ⅱ": "农林牧渔", "农业综合Ⅲ": "农林牧渔",
    "动物保健Ⅱ": "农林牧渔", "动物保健Ⅲ": "农林牧渔",
    "宠物食品": "农林牧渔",
    # ── 家用电器 ──
    "家用电器": "家用电器",
    "白色家电": "家用电器",
    "黑色家电": "家用电器",
    "其他黑色家电": "家用电器",
    "厨卫电器": "家用电器",
    "厨房电器": "家用电器", "卫浴电器": "家用电器",
    "小家电": "家用电器",
    "厨房小家电": "家用电器",
    "个护小家电": "家用电器",
    "清洁小家电": "家用电器",
    "空调": "家用电器",
    "冰洗": "家用电器", "彩电": "家用电器",
    "家电零部件Ⅱ": "家用电器", "家电零部件Ⅲ": "家用电器",
    "其他家电Ⅱ": "家用电器", "其他家电Ⅲ": "家用电器",
    "照明设备Ⅱ": "家用电器",
    # ── 纺织服饰 ──
    "纺织服饰": "纺织服饰",
    "纺织制造": "纺织服饰",
    "纺织鞋类制造": "纺织服饰",
    "棉纺": "纺织服饰", "辅料": "纺织服饰",
    "印染": "纺织服饰",
    "其他纺织": "纺织服饰",
    "服装家纺": "纺织服饰",
    "家纺": "纺织服饰",
    "非运动服装": "纺织服饰",
    "运动服装": "纺织服饰",
    "鞋帽及其他": "纺织服饰",
    # ── 轻工制造 ──
    "轻工制造": "轻工制造",
    "造纸": "轻工制造",
    "大宗用纸": "轻工制造",
    "特种纸": "轻工制造",
    "生活用纸": "轻工制造",
    "包装印刷": "轻工制造",
    "纸包装": "轻工制造",
    "塑料包装": "轻工制造",
    "金属包装": "轻工制造",
    "综合包装": "轻工制造",
    "印刷": "轻工制造",
    "家居用品": "轻工制造",
    "成品家居": "轻工制造",
    "定制家居": "轻工制造",
    "瓷砖地板": "轻工制造",
    "其他家居用品": "轻工制造",
    "卫浴制品": "轻工制造",
    "文娱用品": "轻工制造",
    "文化用品": "轻工制造",
    "娱乐用品": "轻工制造",
    "饰品": "轻工制造",
    "钟表珠宝": "轻工制造",
    "其他饰品": "轻工制造",
    # ── 社会服务 ──
    "社会服务": "社会服务",
    "酒店餐饮": "社会服务",
    "酒店": "社会服务", "餐饮": "社会服务",
    "旅游及景区": "社会服务",
    "旅游综合": "社会服务",
    "人工景区": "社会服务", "自然景区": "社会服务",
    "教育": "社会服务",
    "培训教育": "社会服务",
    "学历教育": "社会服务",
    "教育运营及其他": "社会服务",
    "体育Ⅱ": "社会服务", "体育Ⅲ": "社会服务",
    "专业服务": "社会服务",
    "检测服务": "社会服务",
    "会展服务": "社会服务",
    "人力资源服务": "社会服务",
    "其他专业服务": "社会服务",
    # ── 公用事业 ──
    "公用事业": "公用事业",
    "电力": "公用事业",
    "火力发电": "公用事业",
    "水力发电": "公用事业",
    "风力发电": "公用事业",
    "光伏发电": "公用事业",
    "核力发电": "公用事业",
    "其他能源发电": "公用事业",
    "电能综合服务": "公用事业",
    "燃气Ⅱ": "公用事业", "燃气Ⅲ": "公用事业",
    "热力服务": "公用事业",
    # ── 环保 ──
    "环保": "环保",
    "环境治理": "环保",
    "大气治理": "环保",
    "固废治理": "环保",
    "水务及水治理": "环保",
    "综合环境治理": "环保",
    "环保设备Ⅱ": "环保", "环保设备Ⅲ": "环保",
    # ── 美容护理 ──
    "美容护理": "美容护理",
    "化妆品": "美容护理",
    "化妆品制造及其他": "美容护理",
    "品牌化妆品": "美容护理",
    "个护用品": "美容护理",
    "洗护用品": "美容护理",
    # ── 综合 ──
    "综合": "综合",
    "综合Ⅱ": "综合", "综合Ⅲ": "综合",
}

# 二级/三级 → 一级行业映射（归一化后的一级行业集合）
NORMALIZED_INDUSTRIES: set[str] = set(_INDUSTRY_NORMALIZE.values())

# 31 个申万一级行业标准排序
SHENWAN_SECTORS: list[str] = [
    "农林牧渔", "食品饮料", "纺织服饰", "轻工制造", "医药生物",
    "公用事业", "交通运输", "房地产", "商贸零售", "社会服务",
    "银行", "非银金融",
    "建筑材料", "建筑装饰", "电力设备", "机械设备", "国防军工",
    "汽车", "家用电器",
    "有色金属", "钢铁", "电子", "计算机", "传媒", "通信",
    "煤炭", "石油石化", "基础化工", "环保", "美容护理",
    "综合",
]


def normalize_industry(raw: str) -> str:
    """归一化行业名称为一级行业标准名称

    API 返回的行业名可能是二级（"银行Ⅱ"）或三级（"白酒Ⅲ"），
    需要归一化到一级行业（如"银行"、"食品饮料"）。

    Args:
        raw: API 返回的原始行业名称

    Returns:
        一级行业标准名称，未找到映射时返回原始值
    """
    return _INDUSTRY_NORMALIZE.get(raw, raw)


# ── 产业链位置映射 ──────────────────────────────────────────────────────

INDUSTRY_CHAIN_MAP: dict[str, IndustryChainPosition] = {
    # ── 上游（资源采掘/原材料） ──
    "煤炭":              IndustryChainPosition.UPSTREAM,
    "石油石化":          IndustryChainPosition.UPSTREAM,
    "有色金属":          IndustryChainPosition.UPSTREAM,
    "钢铁":              IndustryChainPosition.UPSTREAM,
    "基础化工":          IndustryChainPosition.UPSTREAM,
    # ── 中游（制造/加工/组装） ──
    "电力设备":          IndustryChainPosition.MIDSTREAM,
    "机械设备":          IndustryChainPosition.MIDSTREAM,
    "国防军工":          IndustryChainPosition.MIDSTREAM,
    "汽车":              IndustryChainPosition.MIDSTREAM,
    "家用电器":          IndustryChainPosition.MIDSTREAM,
    "电子":              IndustryChainPosition.MIDSTREAM,
    "计算机":            IndustryChainPosition.MIDSTREAM,
    "通信":              IndustryChainPosition.MIDSTREAM,
    "轻工制造":          IndustryChainPosition.MIDSTREAM,
    "纺织服饰":          IndustryChainPosition.MIDSTREAM,
    "建筑材料":          IndustryChainPosition.MIDSTREAM,
    "建筑装饰":          IndustryChainPosition.MIDSTREAM,
    "环保":              IndustryChainPosition.MIDSTREAM,
    "美容护理":          IndustryChainPosition.MIDSTREAM,
    # ── 下游（品牌/渠道/服务/消费） ──
    "食品饮料":          IndustryChainPosition.DOWNSTREAM,
    "医药生物":          IndustryChainPosition.DOWNSTREAM,
    "商贸零售":          IndustryChainPosition.DOWNSTREAM,
    "房地产":            IndustryChainPosition.DOWNSTREAM,
    "传媒":              IndustryChainPosition.DOWNSTREAM,
    "社会服务":          IndustryChainPosition.DOWNSTREAM,
    "公用事业":          IndustryChainPosition.DOWNSTREAM,
    "交通运输":          IndustryChainPosition.DOWNSTREAM,
    "农林牧渔":          IndustryChainPosition.DOWNSTREAM,
    # ── 金融（特殊行业） ──
    "银行":              IndustryChainPosition.FINANCIAL,
    "非银金融":          IndustryChainPosition.FINANCIAL,
    # ── 综合/未知 ──
    "综合":              IndustryChainPosition.OTHER,
}


def classify_chain_position(industry: str) -> IndustryChainPosition:
    """获取行业对应的产业链位置

    Args:
        industry: 一级行业名称（已归一化）

    Returns:
        产业链位置，未映射时返回 OTHER
    """
    return INDUSTRY_CHAIN_MAP.get(industry, IndustryChainPosition.OTHER)


# ── 行业关键指标注册表 ────────────────────────────────────────────────

# 结构: 行业名 → [指标 ID 列表]
# 每个行业选 5-10 个最关键的指标，按优先级排序
# 选择逻辑：排除对该行业无意义的指标，保留最能反映该行业经营状况的

REGISTRY: dict[str, list[str]] = {
    # ── 金融 ──
    "银行": [
        "pe", "pb", "roe", "eps", "debt_ratio",
        "roa", "net_profit_growth", "operating_cf_per_share",
    ],
    "非银金融": [
        "pe", "pb", "roe", "eps", "roa",
        "net_profit_growth", "debt_ratio", "operating_cf_per_share",
    ],

    # ── 上游（资源采掘） ──
    "煤炭": [
        "pe", "roe", "eps", "operating_cf_per_share",
        "gross_margin", "debt_ratio", "asset_turnover",
    ],
    "石油石化": [
        "pe", "roe", "eps", "operating_cf_per_share",
        "gross_margin", "debt_ratio", "revenue_growth",
    ],
    "有色金属": [
        "pe", "roe", "eps", "gross_margin",
        "debt_ratio", "operating_cf_per_share", "revenue_growth",
    ],
    "钢铁": [
        "pb", "roe", "eps", "gross_margin",
        "debt_ratio", "asset_turnover", "operating_cf_per_share",
    ],
    "基础化工": [
        "pe", "roe", "eps", "gross_margin",
        "debt_ratio", "inventory_turnover", "revenue_growth",
    ],

    # ── 中游（制造加工） ──
    "电力设备": [
        "pe", "roe", "eps", "revenue_growth",
        "gross_margin", "debt_ratio", "current_ratio",
    ],
    "机械设备": [
        "pe", "roe", "eps", "gross_margin",
        "inventory_turnover", "debt_ratio", "revenue_growth",
    ],
    "国防军工": [
        "pe", "roe", "eps", "revenue_growth",
        "gross_margin", "net_profit_growth", "current_ratio",
    ],
    "汽车": [
        "pe", "roe", "eps", "gross_margin",
        "inventory_turnover", "debt_ratio", "revenue_growth",
    ],
    "家用电器": [
        "pe", "roe", "eps", "gross_margin",
        "inventory_turnover", "net_profit_margin", "revenue_growth",
    ],
    "电子": [
        "pe", "roe", "eps", "gross_margin",
        "revenue_growth", "current_ratio", "quick_ratio",
    ],
    "计算机": [
        "pe", "roe", "eps", "gross_margin",
        "revenue_growth", "net_profit_margin", "current_ratio",
    ],
    "通信": [
        "pe", "roe", "eps", "revenue_growth",
        "gross_margin", "net_profit_growth", "operating_cf_per_share",
    ],
    "轻工制造": [
        "pe", "roe", "eps", "gross_margin",
        "inventory_turnover", "debt_ratio", "net_profit_margin",
    ],
    "纺织服饰": [
        "pe", "roe", "eps", "gross_margin",
        "inventory_turnover", "debt_ratio", "net_profit_margin",
    ],
    "建筑材料": [
        "pe", "roe", "eps", "gross_margin",
        "debt_ratio", "asset_turnover", "current_ratio",
    ],
    "建筑装饰": [
        "pe", "roe", "eps", "debt_ratio",
        "current_ratio", "revenue_growth", "gross_margin",
    ],
    "环保": [
        "pe", "roe", "eps", "revenue_growth",
        "current_ratio", "debt_ratio", "gross_margin",
    ],
    "美容护理": [
        "pe", "roe", "eps", "gross_margin",
        "net_profit_margin", "revenue_growth", "current_ratio",
    ],

    # ── 下游（品牌/渠道/服务/消费） ──
    "食品饮料": [
        "pe", "roe", "eps", "gross_margin",
        "net_profit_margin", "revenue_growth", "operating_cf_per_share",
    ],
    "医药生物": [
        "pe", "roe", "eps", "revenue_growth",
        "gross_margin", "current_ratio", "net_profit_margin",
    ],
    "商贸零售": [
        "pe", "roe", "eps", "gross_margin",
        "net_profit_margin", "inventory_turnover", "asset_turnover",
    ],
    "房地产": [
        "pe", "pb", "roe", "eps",
        "debt_ratio", "current_ratio", "asset_turnover",
    ],
    "传媒": [
        "pe", "roe", "eps", "gross_margin",
        "net_profit_margin", "revenue_growth", "current_ratio",
    ],
    "社会服务": [
        "pe", "roe", "eps", "revenue_growth",
        "gross_margin", "net_profit_margin", "current_ratio",
    ],
    "公用事业": [
        "pe", "roe", "eps", "debt_ratio",
        "current_ratio", "operating_cf_per_share", "gross_margin",
    ],
    "交通运输": [
        "pe", "roe", "eps", "debt_ratio",
        "current_ratio", "operating_cf_per_share", "asset_turnover",
    ],
    "农林牧渔": [
        "pe", "roe", "eps", "revenue_growth",
        "gross_margin", "debt_ratio", "operating_cf_per_share",
    ],

    # ── 综合 ──
    "综合": [
        "pe", "roe", "eps", "revenue_growth",
        "debt_ratio", "gross_margin",
    ],
}


__all__ = [
    "INDICATOR_DEFS",
    "INDICATOR_DEFS_MAP",
    "INDUSTRY_CHAIN_MAP",
    "NORMALIZED_INDUSTRIES",
    "REGISTRY",
    "SHENWAN_SECTORS",
    "IndustryChainPosition",
    "IndicatorDef",
    "classify_chain_position",
    "normalize_industry",
]
