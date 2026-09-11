import { DownOutlined, SearchOutlined } from '@ant-design/icons';
import { loadDictionaryByName, type DictionaryOption } from '@shared/api/dictionaries';
import { getFilterPresetsApiValuationSensitivityFilterPresetsGet } from '@shared/api/generated/services.gen';
import type { ValuationFilterPresetModel } from '@shared/api/generated/types.gen';
import { Alert, Button, DatePicker, Dropdown, Select, Space } from 'antd';
import dayjs from 'dayjs';
import { useEffect, useState } from 'react';


// Helper functions for universal interval handling
const getPickerType = (interval?: 'daily' | 'weekly' | 'monthly' | 'yearly') => {
  switch (interval) {
    case 'daily':
      return 'date';
    case 'weekly':
      return 'week';
    case 'yearly':
      return 'year';
    default:
      return 'month';
  }
};

export const formatPeriodBoundary = (
  date: dayjs.Dayjs,
  interval: 'daily' | 'weekly' | 'monthly' | 'yearly' | undefined,
  boundary: 'from' | 'to',
) => {
  switch (interval) {
    case 'daily':
      return date.format('YYYY-MM-DD');
    case 'weekly':
      return date[boundary === 'from' ? 'startOf' : 'endOf']('week').format('YYYY-MM-DD');
    case 'yearly':
      return date[boundary === 'from' ? 'startOf' : 'endOf']('year').format('YYYY-MM-DD');
    default:
      return date[boundary === 'from' ? 'startOf' : 'endOf']('month').format('YYYY-MM-DD');
  }
};

export interface ValuationScopeFilterValue {
  markets: string[];
  products: string[];
  supplyPaths: string[];
  glAccounts: string[];
  periodFrom: string;
  periodTo: string;
  /** Time interval for period date pickers: 'daily', 'weekly', 'monthly', or 'yearly' (default: 'monthly') */
  interval?: 'daily' | 'weekly' | 'monthly' | 'yearly';
}

export type ValuationPeriodMode = 'valuations' | 'payments';

interface ValuationScopeFilterProps {
  value: ValuationScopeFilterValue;
  onChange: (value: ValuationScopeFilterValue) => void;
  onPresetPeriodModeChange?: (periodMode: ValuationPeriodMode) => void;
  onApply?: () => void;
  loading?: boolean;
  applyLabel?: string;
  onPresetObservationDateChange?: (observationDate: string) => void;
}

export const VALUATION_PERIOD_MODE_OPTIONS = [
  { value: 'valuations', label: 'Valuations' },
  { value: 'payments', label: 'Payments' },
] as const;

const parseIsoDate = (value: string) => {
  if (!value) {
    return null;
  }

  const parsed = dayjs(value);
  if (!parsed.isValid()) {
    return null;
  }

  return parsed.format('YYYY-MM-DD') === value ? parsed : null;
};

const parseMonthValue = (value: string) => {
  const parsed = parseIsoDate(value);
  return parsed ? parsed.startOf('month') : null;
};

const parseDayValue = (value: string) => {
  const parsed = parseIsoDate(value);
  return parsed;
};

export const valuationScopeFromPreset = (
  preset: ValuationFilterPresetModel,
  currentValue: ValuationScopeFilterValue,
): ValuationScopeFilterValue => ({
  markets: [...(preset.filters.markets || [])],
  products: [...(preset.filters.products || [])],
  supplyPaths: [...(preset.filters.supply_paths || [])],
  glAccounts: [...(preset.filters.gl_accounts || [])],
  periodFrom: preset.filters.period_from || currentValue.periodFrom,
  periodTo: preset.filters.period_to || currentValue.periodTo,
  interval: currentValue.interval,
});

const ValuationScopeFilter = ({
  value,
  onChange,
  onApply,
  loading = false,
  applyLabel = 'Применить',
  onPresetObservationDateChange,
  onPresetPeriodModeChange,
}: ValuationScopeFilterProps) => {
  const [marketOptions, setMarketOptions] = useState<DictionaryOption[]>([]);
  const [productOptions, setProductOptions] = useState<DictionaryOption[]>([]);
  const [supplyPathOptions, setSupplyPathOptions] = useState<DictionaryOption[]>([]);
  const [glAccountOptions, setGlAccountOptions] = useState<DictionaryOption[]>([]);
  const [dictionariesLoading, setDictionariesLoading] = useState(false);
  const [dictionariesError, setDictionariesError] = useState<string | null>(null);
  const [presetOptions, setPresetOptions] = useState<ValuationFilterPresetModel[]>([]);
  const [presetsLoading, setPresetsLoading] = useState(false);
  const [presetsError, setPresetsError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadDictionaries = async () => {
      setDictionariesLoading(true);
      setDictionariesError(null);

      try {
        const [markets, products, supplyPaths, glAccounts] = await Promise.all([
          loadDictionaryByName('delivery_markets'),
          loadDictionaryByName('products'),
          loadDictionaryByName('supply_paths'),
          loadDictionaryByName('gl_accounts'),
        ]);

        if (cancelled) {
          return;
        }

        setMarketOptions(markets);
        setProductOptions(products);
        setSupplyPathOptions(supplyPaths);
        setGlAccountOptions(glAccounts);
      } catch (error: any) {
        if (!cancelled) {
          setDictionariesError(error?.message || 'Не удалось загрузить фильтры');
        }
      } finally {
        if (!cancelled) {
          setDictionariesLoading(false);
        }
      }
    };

    loadDictionaries();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadPresets = async () => {
      setPresetsLoading(true);
      setPresetsError(null);

      try {
        const response = await getFilterPresetsApiValuationSensitivityFilterPresetsGet();
        if (!cancelled) {
          setPresetOptions(response);
        }
      } catch (error: any) {
        if (!cancelled) {
          setPresetsError(error?.body?.detail || error?.message || 'Не удалось загрузить frequently used filters');
        }
      } finally {
        if (!cancelled) {
          setPresetsLoading(false);
        }
      }
    };

    loadPresets();

    return () => {
      cancelled = true;
    };
  }, []);

  const useIntervalForDayPicker = value.interval === 'daily' || value.interval === 'weekly';
  const validDateGranularity = value.interval === 'weekly' ? 'week' : value.interval === 'daily' ? 'day' : 'month';

  const periodFromValue = useIntervalForDayPicker ? parseDayValue(value.periodFrom) : parseMonthValue(value.periodFrom);
  const periodToValue = useIntervalForDayPicker ? parseDayValue(value.periodTo) : parseMonthValue(value.periodTo);
  const hasValidRange = Boolean(periodFromValue && periodToValue && !periodFromValue.isAfter(periodToValue, validDateGranularity));
  const isApplyDisabled = loading || dictionariesLoading || !hasValidRange;
  const presetMenuItems = presetOptions.map((preset) => ({
    key: preset.id,
    label: (
      <div>
        <div>{preset.name}</div>
        {preset.description ? <div style={{ fontSize: 12, color: '#8c8c8c' }}>{preset.description}</div> : null}
      </div>
    ),
  }));

  const update = (patch: Partial<ValuationScopeFilterValue>) => onChange({ ...value, ...patch });

  const updatePeriodBoundary = (
    boundary: 'periodFrom' | 'periodTo',
    date: dayjs.Dayjs | null,
  ) => {
    const formattedDate = date
      ? formatPeriodBoundary(date, value.interval, boundary === 'periodFrom' ? 'from' : 'to')
      : '';
    update({ [boundary]: formattedDate });
  };

  const applyPreset = (presetId: string) => {
    const preset = presetOptions.find((item) => item.id === presetId);
    if (!preset) {
      return;
    }

    onChange(valuationScopeFromPreset(preset, value));
    if (preset.filters.observation_date) {
      onPresetObservationDateChange?.(preset.filters.observation_date);
    }
    onPresetPeriodModeChange?.(preset.filters.period_mode || 'valuations');
  };

  return (
    <div>
      <Space wrap size="middle" style={{ marginBottom: dictionariesError ? 12 : 0 }}>
        <Dropdown
          menu={{
            items: presetMenuItems,
            onClick: ({ key }) => applyPreset(String(key)),
          }}
          trigger={["click"]}
          disabled={presetsLoading || presetOptions.length === 0}
        >
          <Button icon={<DownOutlined />} loading={presetsLoading}>
            Фильтры
          </Button>
        </Dropdown>
        <Select
          mode="multiple"
          allowClear
          maxTagCount="responsive"
          style={{ width: 220 }}
          placeholder="Markets"
          value={value.markets}
          onChange={(markets) => update({ markets })}
          options={marketOptions}
          loading={dictionariesLoading}
        />
        <Select
          mode="multiple"
          allowClear
          maxTagCount="responsive"
          style={{ width: 220 }}
          placeholder="Supply Paths"
          value={value.supplyPaths}
          onChange={(supplyPaths) => update({ supplyPaths })}
          options={supplyPathOptions}
          loading={dictionariesLoading}
        />
        <Select
          mode="multiple"
          allowClear
          maxTagCount="responsive"
          style={{ width: 220 }}
          placeholder="Products"
          value={value.products}
          onChange={(products) => update({ products })}
          options={productOptions}
          loading={dictionariesLoading}
        />
        <Select
          mode="multiple"
          allowClear
          maxTagCount="responsive"
          style={{ width: 220 }}
          placeholder="GL accounts"
          value={value.glAccounts}
          onChange={(glAccounts) => update({ glAccounts })}
          options={glAccountOptions}
          loading={dictionariesLoading}
        />
        <DatePicker
          picker={getPickerType(value.interval)}
          style={{ width: 150 }}
          placeholder={useIntervalForDayPicker ? 'From' : 'Period from'}
          value={periodFromValue}
          onChange={(date) => updatePeriodBoundary('periodFrom', date)}
          status={hasValidRange ? undefined : 'error'}
        />
        <DatePicker
          picker={getPickerType(value.interval)}
          style={{ width: 150 }}
          placeholder={useIntervalForDayPicker ? 'To' : 'Period to'}
          value={periodToValue}
          onChange={(date) => updatePeriodBoundary('periodTo', date)}
          status={hasValidRange ? undefined : 'error'}
        />
        {onApply && (
          <Button
            type="primary"
            icon={<SearchOutlined />}
            onClick={onApply}
            loading={loading}
            disabled={isApplyDisabled}
          >
            {applyLabel}
          </Button>
        )}
      </Space>
      {dictionariesError && (
        <Alert
          message="Ошибка загрузки фильтров"
          description={dictionariesError}
          type="error"
          showIcon
        />
      )}
      {presetsError && (
        <Alert
          message="Ошибка загрузки frequently used filters"
          description={presetsError}
          type="error"
          showIcon
          style={{ marginTop: 12 }}
        />
      )}
    </div>
  );
};

export default ValuationScopeFilter;
