// The fair-value model's assumptions, Classic's fields word for word (static/valuation.js FIELDS): where each lives in
// a run's request, how it is shown, and which default rationale explains it. Shared by the editor (pages/dcf.js) and by
// Milo's proposal card (core/milo-text.js), which accepts only a key listed here (Classic parity B7d).
export const FIELDS = [
  { group: 'Growth', key: 'growth.y1', label: 'Revenue growth, first year', unit: '%', why: 'growth.y1' },
  { group: 'Growth', key: 'growth.y2', label: 'Revenue growth, second year', unit: '%', why: 'growth.y2', blank: 'fades from year 1' },
  { group: 'Growth', key: 'growth.fade_years', label: 'Years for growth to fade to the long run', unit: 'yrs', step: 1, why: 'growth.fade_years', blank: 'the whole forecast' },
  { group: 'Growth', key: 'terminal.growth', label: 'Growth after the forecast, forever', unit: '%', why: 'terminal.growth' },
  { group: 'Growth', key: 'horizon', label: 'Forecast years', unit: 'yrs', step: 1 },
  { group: 'Profitability', key: 'margin.start', label: 'Operating margin, first year', unit: '%', why: 'margin.start' },
  { group: 'Profitability', key: 'margin.target', label: 'Operating margin it settles at', unit: '%', why: 'margin.target' },
  { group: 'Profitability', key: 'margin.years', label: 'Years to get there', unit: 'yrs', step: 1 },
  { group: 'Reinvestment', key: 'capex_pct.start', label: 'Capex, first year (share of revenue)', unit: '%', why: 'capex.start' },
  { group: 'Reinvestment', key: 'capex_pct.target', label: 'Capex it settles at', unit: '%', why: 'capex.target' },
  { group: 'Reinvestment', key: 'capex_pct.years', label: 'Years to get there', unit: 'yrs', step: 1 },
  { group: 'Reinvestment', key: 'dep_rate', label: 'Depreciation (share of last year’s net PP&E)', unit: '%', why: 'dep_rate' },
  { group: 'Reinvestment', key: 'nwc_pct', label: 'Working capital (share of revenue)', unit: '%', why: 'nwc_pct' },
  { group: 'Reinvestment', key: 'terminal.ronic', label: 'Return on new capital after the forecast', unit: '%', why: 'terminal.ronic' },
  { group: 'Taxes', key: 'tax.start', label: 'Tax rate on operating profit, first year', unit: '%', why: 'tax.start' },
  { group: 'Taxes', key: 'tax.terminal', label: 'Long-run tax rate', unit: '%', why: 'tax.terminal' },
  { group: 'Discount rate', key: 'wacc.risk_free', label: 'Risk-free rate (10-year Treasury)', unit: '%', wacc: true },
  { group: 'Discount rate', key: 'wacc.beta_raw', label: 'Beta (raw, before adjustment)', unit: 'x', wacc: true, step: 0.01 },
  { group: 'Discount rate', key: 'wacc.erp', label: 'Equity risk premium', unit: '%', wacc: true },
  { group: 'Discount rate', key: 'wacc.extra_premium', label: 'Extra premium (size, country, your own)', unit: '%', wacc: true },
  { group: 'Discount rate', key: 'wacc.pre_tax_cost_debt', label: 'Pre-tax cost of debt', unit: '%', wacc: true },
  { group: 'Discount rate', key: 'wacc.marginal_tax', label: 'Tax rate for the interest shield', unit: '%', wacc: true },
  { group: 'Discount rate', key: 'wacc.debt_weight', label: 'Debt weight (blank: today’s market weights)', unit: '%', wacc: true, blank: 'market weights' },
  { group: 'Discount rate', key: 'wacc.override', label: 'Or set the discount rate directly', unit: '%', wacc: true, blank: 'built from the parts above' },
  { group: 'Cross-check', key: 'exit_multiple', label: 'Exit EV/EBITDA (cross-check only)', unit: 'x', why: 'exit_multiple', step: 0.1 },
];
export const GROUPS = ['Growth', 'Profitability', 'Reinvestment', 'Taxes', 'Discount rate', 'Cross-check'];
/** A proposal's value as the model takes it: a percentage field reads 25 or 25% as 0.25, a fraction (0.25) as itself. */
export function proposedValue(f, value, unit = '') {
  return f.unit === '%' ? (unit === '%' || Math.abs(value) > 1.5 ? value / 100 : value) : value;
}
