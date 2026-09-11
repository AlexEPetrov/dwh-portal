import { getObservationDatesApiValuationResultsObservationDatesGet } from '@shared/api/generated/services.gen';
import type { ObservationDateInfo } from '@shared/api/generated/types.gen';
import { Select, Spin, Typography } from 'antd';
import { useEffect, useState } from 'react';

interface MultiObservationDateSelectProps {
  /** Selected observation dates (YYYY-MM-DD). */
  value: string[];
  onChange: (value: string[]) => void;
  /** Select width. Default: 320. */
  width?: number;
  /** Label text. Default: 'Даты наблюдения:'. */
  label?: string;
  /** Max tag count shown before collapsing. Default: 'responsive'. */
  maxTagCount?: number | 'responsive';
  /** Run mode used to filter available dates. Default: 'simulation'. */
  runMode?: 'simulation' | 'deterministic';
  /** Sort order. Default: 'desc' (latest first). */
  order?: 'asc' | 'desc';
}

/**
 * Multi-select for observation dates.
 *
 * Reuses the canonical `/results/observation-dates` endpoint (same source as
 * `ObservationDateScenarioControl`). The dates returned there are simulation
 * partition dates (fact_simulation). The component is run-mode agnostic on the
 * client side — backend partition filtering happens server-side; here we only
 * present the available dates as a multi-select.
 *
 * Self-initializes the available-dates list on mount.
 */
const MultiObservationDateSelect = ({
  value,
  onChange,
  width = 320,
  label = 'Даты наблюдения:',
  maxTagCount = 'responsive',
  runMode = 'simulation',
  order = 'desc',
}: MultiObservationDateSelectProps) => {
  const [availableDates, setAvailableDates] = useState<ObservationDateInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getObservationDatesApiValuationResultsObservationDatesGet()
      .then((response) => {
        if (cancelled) return;
        const dates = response?.observation_dates || [];
        const sorted = [...dates].sort((a, b) =>
          order === 'desc' ? b.date.localeCompare(a.date) : a.date.localeCompare(b.date)
        );
        setAvailableDates(sorted);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.message || 'Не удалось загрузить даты наблюдения');
        setAvailableDates([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [order, runMode]);

  const options = availableDates.map((d) => ({
    label: d.date,
    value: d.date,
  }));

  return (
    <>
      {label && <Typography.Text strong>{label}</Typography.Text>}
      <Select
        mode="multiple"
        allowClear
        style={{ width, minWidth: 220 }}
        placeholder="Выберите даты наблюдения"
        value={value}
        onChange={onChange}
        options={options}
        loading={loading}
        maxTagCount={maxTagCount}
        notFoundContent={loading ? <Spin size="small" /> : error || 'Нет данных'}
        showSearch
        optionFilterProp="label"
      />
    </>
  );
};

export default MultiObservationDateSelect;
