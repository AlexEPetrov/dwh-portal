import { Select } from 'antd';

export type ReportingCurrency = 'usd' | 'eur' | 'rub' | 'contract';

export const CURRENCY_OPTIONS = [
  { value: 'usd', label: 'USD' },
  { value: 'eur', label: 'EUR' },
  { value: 'rub', label: 'RUB' },
  { value: 'contract', label: 'В валюте контракта' },
] as const;

interface CurrencySelectorProps {
  value: ReportingCurrency;
  onChange: (value: ReportingCurrency) => void;
  disabled?: boolean;
  /** Currency values to exclude from the dropdown (e.g. ['contract']) */
  exclude?: ReportingCurrency[];
}

/**
 * Shared currency selector for reporting currency selection.
 * Used across valuation results, sensitivity, and other reporting screens.
 */
const CurrencySelector = ({ value, onChange, disabled, exclude }: CurrencySelectorProps) => {
  const options = exclude
    ? CURRENCY_OPTIONS.filter((opt) => !exclude.includes(opt.value))
    : CURRENCY_OPTIONS;

  return (
    <Select
      style={{ width: 120 }}
      value={value}
      onChange={onChange}
      options={options as unknown as { value: string; label: string }[]}
      disabled={disabled}
      placeholder="Валюта"
    />
  );
};

export default CurrencySelector;
