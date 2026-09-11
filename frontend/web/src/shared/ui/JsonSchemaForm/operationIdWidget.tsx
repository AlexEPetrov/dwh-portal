import { getMcmfCatalogApiReportingMcmfCatalogGet } from '@shared/api/generated/services.gen';
import type { McmfCatalogSimulationSet } from '@shared/api/generated/types.gen';
import AutoComplete from 'antd/es/auto-complete';
import Spin from 'antd/es/spin';
import { useEffect, useMemo, useState } from 'react';

type SuggestionGroup = {
  label: string;
  options: Array<{ label: string; value: string }>;
};

/**
 * Editable text input for operation_id with dropdown suggestions from the MCMF catalog.
 *
 * Data source: GET /api/reporting/mcmf/catalog
 * Suggestions are grouped by observation_date for easy browsing.
 *
 * Uses Ant Design AutoComplete so the value remains a plain editable string —
 * the user can freely type, modify, or re-pick at any time (no immutable tag chips).
 *
 * Submitted value format matches what the backend already accepts via
 * _parse_operation_selector_input() — e.g. "20260715/eod".
 */
export const OperationIdSelectWidget = (props: any) => {
  const { value, onChange } = props;
  const [simulations, setSimulations] = useState<McmfCatalogSimulationSet[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(false);

  useEffect(() => {
    let isMounted = true;
    setCatalogLoading(true);

    getMcmfCatalogApiReportingMcmfCatalogGet()
      .then((response) => {
        if (!isMounted) return;
        setSimulations(response.simulations ?? []);
      })
      .catch((err) => {
        if (isMounted) {
          console.warn('OperationIdSelectWidget: failed to load MCMF catalog', err);
          setSimulations([]);
        }
      })
      .finally(() => {
        if (isMounted) setCatalogLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const suggestionGroups: SuggestionGroup[] = useMemo(() => {
    const groups = new Map<string, Array<{ label: string; value: string }>>();
    for (const sim of simulations) {
      const dateKey = sim.key.split('/', 1)[0];
      if (!groups.has(dateKey)) {
        groups.set(dateKey, []);
      }
      groups.get(dateKey)!.push({ label: sim.key, value: sim.key });
    }
    // Sort groups by date descending
    return Array.from(groups.entries())
      .map(([dateKey, options]) => ({ label: dateKey, options }))
      .sort((a, b) => (a.label < b.label ? 1 : -1));
  }, [simulations]);

  // Normalize current value: RJSF may pass null/undefined; AutoComplete expects string.
  const displayValue = value && typeof value === 'string' ? value : '';

  return (
    <AutoComplete
      value={displayValue}
      onChange={(next: string) => onChange(next === '' ? undefined : next)}
      options={suggestionGroups}
      filterOption={(input: string, option: any) => {
        const label = String(option?.label ?? '').toLowerCase();
        return label.includes(input.toLowerCase());
      }}
      allowClear
      style={{ width: '100%' }}
      notFoundContent={catalogLoading ? <Spin size="small" /> : undefined}
      placeholder="Select or type YYYYMMDD/operation_id"
    />
  );
};
