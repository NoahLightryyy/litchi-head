/** Hypothetical product scenarios, not account recommendations. All amounts CNY. */
export function capitalScenario(capital: number, monthlyApi: number, roundTrips: number) {
  if (!Number.isFinite(capital) || capital <= 0 || capital > 1e9
    || !Number.isFinite(monthlyApi) || monthlyApi < 0 || monthlyApi > 1e6
    || !Number.isInteger(roundTrips) || roundTrips < 0 || roundTrips > 1000) {
    throw new Error("请输入有效的本金、研究费和完整买卖次数");
  }
  const commission = Math.round(roundTrips * 2 * Math.max(5, capital * 0.1 * 0.0003) * 100) / 100;
  return {capital, core: capital * .6, theme: capital * .2, cash: capital * .2,
    loss: capital * .19, uninvestedLoss: capital * .12, commission,
    monthlyCost: commission + monthlyApi, monthlyCostPct: (commission + monthlyApi) / capital * 100,
    minimumOrderPct: 3000 / capital * 100, themeExecutable: 3000 <= capital * .2};
}
