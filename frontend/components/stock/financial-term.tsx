"use client";

import { useRef, useState } from "react";

const terms: Record<string, [string, string, string]> = {
  roe: ["净资产收益率（ROE）", "衡量股东投入的净资产产生利润的能力，通常以净利润除以净资产计算。", "用于比较资本回报。高负债或很小的净资产也会推高 ROE；加权、摊薄及年化口径需保持一致。"],
  roa: ["总资产收益率（ROA）", "衡量公司利用全部资产创造收益的效率，收益与资产的比率。", "用于观察资产使用效率。不同来源可能使用净利润或其他利润口径；不能直接与 ROE 等同。"],
  gross_margin: ["毛利率", "（营业收入 − 营业成本）÷ 营业收入 × 100%。", "反映产品或服务扣除直接营业成本后的盈利空间。尚未扣除销售、管理、研发、利息和所得税，不等于净利润率。"],
  net_profit_margin: ["净利率", "净利润 ÷ 营业收入 × 100%，表示每一元收入最终留下多少利润。", "用于看整体盈利能力，需同时留意一次性收益、税率和利润归属口径。"],
  revenue_growth: ["营收增长率", "本报告期累计营业收入相对上年同期的变化比例。", "观察业务规模增长；应比较同长度报告期，增长也可能来自收购或价格上涨。"],
  net_profit_growth: ["净利润增长率", "本报告期净利润相对上年同期的变化比例。", "观察盈利增长；上期利润接近零或为负时百分比容易失真，要结合利润金额。"],
  debt_ratio: ["资产负债率", "总负债 ÷ 总资产 × 100%。", "观察资产中由负债支持的比例。需结合行业、债务期限和现金流，不能单凭高低判断安全。"],
  current_ratio: ["流动比率", "流动资产 ÷ 流动负债。", "观察短期偿债资源。存货与应收账款未必能及时变现，不同经营模式没有统一合格线。"],
  quick_ratio: ["速动比率", "速动资产 ÷ 流动负债；常从流动资产中扣除存货等变现较慢的项目。", "比流动比率更谨慎地观察短期偿债能力，速动资产具体扣除项以来源口径为准。"],
  eps: ["每股收益（EPS）", "按相应股数口径分摊到每股的利润。本指标源为摊薄每股收益。", "用于观察每股盈利和估值，不能直接视为可分红金额；不混用基本、摊薄和稀释口径。"],
  book_value_per_share: ["每股净资产", "相应净资产 ÷ 股数，反映每股对应的账面净资产。", "辅助理解市净率；账面价值不等于清算价值或市场价值，调整口径以来源为准。"],
  operating_cf_per_share: ["每股经营性现金流", "经营活动现金流量净额 ÷ 相应股数。", "观察主营经营现金回收能力，结合 EPS 看盈利含金量；不等于自由现金流或可分红现金。"],
  inventory_turnover: ["存货周转率", "通常为营业成本 ÷ 平均存货，单位为次。", "观察存货周转速度。季节性、行业和报告期长短影响较大，周转快不一定代表供货充足。"],
  asset_turnover: ["总资产周转率", "营业收入 ÷ 平均总资产，单位为次。", "观察资产带来收入的效率。轻资产与重资产行业应分开比较，半年累计不能直接与全年比较。"],
  pe: ["市盈率（PE）", "股价 ÷ 每股收益，或相同股本范围的市值 ÷ 净利润。", "衡量价格相对利润的倍数。需区分静态、滚动和预测口径；亏损或极小利润时不适合直接比较。"],
  pb: ["市净率（PB）", "股价 ÷ 每股净资产。", "衡量价格相对账面净资产的倍数；需结合资产质量、盈利能力和无形资产。"],
  ps: ["市销率（PS）", "相同范围的市值 ÷ 营业收入。", "衡量价格相对收入规模的倍数，不能体现成本、盈利与债务状况。"],
  market_cap: ["总市值", "按适用股本范围及报价计算的公司股权市场价值。", "用于观察规模和估值。跨市场上市时不能随意把某一市场股价乘以全部股本。"],
  report_date: ["报告期", "财务报表所覆盖期间的截止日期，不是公告日期或实时行情时间。", "利润与现金流通常为年初至期末累计，资产负债为期末时点。比较时须保持报告期长度和口径一致。"],
};

export function FinancialTerm({ id, label }: { id: string; label: string }) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const close = () => { setOpen(false); trigger.current?.focus(); };
  const term = terms[id];
  if (!term) return <span>{label}</span>;
  return <span className="inline-block">
    <button ref={trigger} type="button" aria-label={`了解${label}`} aria-haspopup="dialog" onClick={() => setOpen(true)} className="text-left underline decoration-dotted underline-offset-4 hover:text-accent-green">{label} ⓘ</button>
    {open && <dialog open aria-label={term[0]} onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); close(); } }} className="fixed inset-0 z-50 m-auto w-[min(90vw,32rem)] rounded-xl border border-bg-tertiary bg-bg-primary p-6 text-left text-sm text-text-primary shadow-xl whitespace-normal">
      <div className="flex items-center justify-between gap-4"><strong>{term[0]}</strong><button type="button" autoFocus onClick={close} className="rounded border px-3 py-1">关闭</button></div>
      <p className="mt-4 font-semibold">含义与计算</p><p className="mt-1">{term[1]}</p>
      <p className="mt-4 font-semibold">用途与解读</p><p className="mt-1">{term[2]}</p>
      <p className="mt-4 text-xs text-text-muted">以上为指标概念说明；具体数值以报告期及数据源口径为准，单项指标不构成买卖结论。</p>
    </dialog>}
  </span>;
}
