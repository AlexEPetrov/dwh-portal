import { Select, Space, Typography } from 'antd';

export type SimulationPeriodMode = 'valuations' | 'payments' | 'prices';
export type SimulationCurrencyTarget = 'value_rub' | 'value_usd' | 'price_rub' | 'price_usd';
export type SimulationReportingCurrency = 'rub' | 'usd';

const VALUATION_CURRENCY_OPTIONS: { value: 'value_rub' | 'value_usd'; label: string }[] = [
  { value: 'value_usd', label: 'USD' },
  { value: 'value_rub', label: 'RUB' },
];

const PRICE_CURRENCY_OPTIONS: { value: 'price_rub' | 'price_usd'; label: string }[] = [
  { value: 'price_usd', label: 'USD' },
  { value: 'price_rub', label: 'RUB' },
];

const PRICE_MODE_CURRENCY_LABEL = 'Валюта (price = sum(target)/sum(volume))';

export const getSimulationCurrencyOptions = (mode: SimulationPeriodMode): { value: SimulationCurrencyTarget; label: string }[] => {
  if (mode === 'prices') return PRICE_CURRENCY_OPTIONS as unknown as { value: SimulationCurrencyTarget; label: string }[];
  return VALUATION_CURRENCY_OPTIONS as unknown as { value: SimulationCurrencyTarget; label: string }[];
};

export const getSimulationCurrencySelectorLabel = (mode: SimulationPeriodMode) => {
  if (mode === 'prices') return PRICE_MODE_CURRENCY_LABEL;
  return 'Валюта';
};

export const normalizeSimulationTargetForPeriodMode = (
  target: SimulationCurrencyTarget,
  mode: SimulationPeriodMode,
): SimulationCurrencyTarget => {
  const currency = target.endsWith('_usd') ? 'usd' : 'rub';
  return mode === 'prices' ? (`price_${currency}` as SimulationCurrencyTarget) : (`value_${currency}` as SimulationCurrencyTarget);
};

export const buildSimulationPeriodModeUpdate = (
  target: SimulationCurrencyTarget,
  periodMode: SimulationPeriodMode,
): { periodMode: SimulationPeriodMode; target: SimulationCurrencyTarget } => ({
  periodMode,
  target: normalizeSimulationTargetForPeriodMode(target, periodMode),
});

export const currencyFromSimulationTarget = (target: SimulationCurrencyTarget): SimulationReportingCurrency => {
  return target.endsWith('_usd') ? 'usd' : 'rub';
};

interface SimulationCurrencyTargetSelectorProps {
  value: SimulationCurrencyTarget;
  periodMode: SimulationPeriodMode;
  onChange: (value: SimulationCurrencyTarget) => void;
  showLabel?: boolean;
}

const SimulationCurrencyTargetSelector = ({
  value,
  periodMode,
  onChange,
  showLabel = true,
}: SimulationCurrencyTargetSelectorProps) => {
  const normalizedValue = normalizeSimulationTargetForPeriodMode(value, periodMode);

  const select = (
    <Select
      style={{ width: 100 }}
      value={normalizedValue}
      onChange={onChange}
      options={getSimulationCurrencyOptions(periodMode)}
    />
  );

  if (!showLabel) return select;

  return (
    <Space size={4}>
      <Typography.Text strong>{getSimulationCurrencySelectorLabel(periodMode)}:</Typography.Text>
      {select}
    </Space>
  );
};

export default SimulationCurrencyTargetSelector;
