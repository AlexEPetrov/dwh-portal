import { loadDictionaryByName, type DictionaryOption } from '@shared/api/dictionaries';
import { getAvailableValuationTypesApiValuationResultsValuationTypesGet, getObservationDatesApiValuationResultsObservationDatesGet } from '@shared/api/generated/services.gen';
import type { ObservationDateInfo, ValuationTypeInfo } from '@shared/api/generated/types.gen';
import { resolveAvailableValuationType, shouldLoadValuationTypes } from '@shared/valuationType';
import { DatePicker, Select, Space, Typography } from 'antd';
import './styles.css';
import dayjs from 'dayjs';
import { useCallback, useEffect, useRef, useState } from 'react';

export interface ObservationDateScenarioControlValue {
  observationDate: string;
  scenario: string | null;
  valuationType: string | null;
}

type RunMode = 'simulation' | 'deterministic';

interface ObservationDateScenarioControlProps {
  value: ObservationDateScenarioControlValue;
  onChange: (value: ObservationDateScenarioControlValue) => void;
  /** Show scenario selector. Default: true. */
  showScenario?: boolean;
  /** Show valuation type selector. Default: true. */
  showValuationType?: boolean;
  /** Label for observation date. Default: 'Дата наблюдения:'. */
  observationDateLabel?: string;
  /** Label for scenario selector. Default: 'Сценарий:'. */
  scenarioLabel?: string;
  /** Label for valuation type selector. Default: 'Вид оценки:'. */
  valuationTypeLabel?: string;
  /** Width of the date picker. Default: 180. */
  datePickerWidth?: number;
  /** Width of the scenario selector. Default: 200. */
  scenarioSelectWidth?: number;
  /** Width of the valuation type selector. Default: 200. */
  valuationTypeSelectWidth?: number;
  /** Allow selecting dates that are not present in simulation result partitions. */
  allowUnavailableDateSelection?: boolean;
  /**
   * Run mode: determines which partition root to scan for valuation types and observation dates.
   * - 'simulation': scans fact_simulation partitions
   * - 'deterministic': scans deterministic partitions
   */
  runMode?: RunMode;
  /**
   * Date selection mode:
   * - 'restricted' (default): Only allow selecting available observation dates from simulation results
   * - 'free': Allow selecting any date (for valuation results without simulations)
   */
  dateSelectionMode?: 'restricted' | 'free';
}

/**
 * Combined control for observation date, valuation type, and scenario selection.
 *
 * Self-initialization flow (when value.observationDate is empty):
 * 1. Fetch available observation dates and auto-select the latest one.
 * 2. Based on the selected date, fetch available valuation types and auto-select the first one.
 * 3. Fetch scenarios and auto-select 'default' if available.
 *
 * All three steps are sequential within a single useEffect, ensuring no race conditions.
 *
 * For ongoing changes:
 * - valuation type API re-fetches when observationDate changes
 * - scenario auto-selection only happens once on mount
 *
 * In 'restricted' mode (default), the observation date picker restricts selection
 * to available partition dates only (for simulation results).
 * In 'free' mode, any date can be selected (for valuation results without simulations).
 *
 * When runMode is specified, only partitions for that run mode are scanned.
 * When runMode is not specified, all partitions are scanned and merged.
 */
const ObservationDateScenarioControl = ({
  value,
  onChange,
  showScenario = true,
  showValuationType = true,
  observationDateLabel = 'Дата наблюдения:',
  scenarioLabel = 'Сценарий:',
  valuationTypeLabel = 'Вид оценки:',
  datePickerWidth = 180,
  scenarioSelectWidth = 200,
  valuationTypeSelectWidth = 200,
  allowUnavailableDateSelection = false,
  runMode,
  dateSelectionMode = 'restricted',
}: ObservationDateScenarioControlProps) => {
  const [availableDates, setAvailableDates] = useState<ObservationDateInfo[]>([]);
  const [_datesLoading, setDatesLoading] = useState(false);
  const [scenarioOptions, setScenarioOptions] = useState<DictionaryOption[]>([]);
  const [scenariosLoading, setScenariosLoading] = useState(false);
  const [valuationTypeOptions, setValuationTypeOptions] = useState<DictionaryOption[]>([]);
  const [valuationTypesLoading, setValuationTypesLoading] = useState(false);

  // Stabilize onChange with ref
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  // Track whether self-initialization has completed (to prevent re-running on every re-render)
  const selfInitializedRef = useRef(false);

  // --- Helper: perform self-initialization ---
  // Calls onChange() exactly once at the end with all fully-resolved values,
  // so parent auto-fire effects see a complete state and don't fire prematurely.
  const performSelfInitialization = useCallback(async () => {
    if (selfInitializedRef.current) return;
    selfInitializedRef.current = true;

    // Step 1: Fetch observation dates and auto-select the latest one.
    // Always fetch dates regardless of dateSelectionMode — it only controls the picker restriction,
    // not whether we should find the best available date for initialization.
    let latestDate = '';
    let dates: ObservationDateInfo[] = [];

    setDatesLoading(true);
    try {
      const response = await getObservationDatesApiValuationResultsObservationDatesGet();
      dates = response?.observation_dates || [];
      setAvailableDates(dates);
    } catch {
      dates = [];
      // Only clear availableDates for restricted mode; free mode doesn't use them for filtering
      if (dateSelectionMode !== 'free') {
        setAvailableDates([]);
      }
    } finally {
      setDatesLoading(false);
    }

    if (dates.length > 0) {
      const sorted = [...dates].sort((a, b) => b.date.localeCompare(a.date));
      latestDate = sorted[0].date;
    } else {
      latestDate = dayjs().format('YYYY-MM-DD');
    }

    // Step 2: Fetch valuation types and auto-select the first one
    let firstValuationTypeName: string | null = null;
    if (showValuationType) {
      setValuationTypesLoading(true);
      try {
        const response = await getAvailableValuationTypesApiValuationResultsValuationTypesGet({
          observationDate: latestDate,
          runMode: runMode ?? 'simulation',
        });
        const types = (response?.valuation_types || []) as ValuationTypeInfo[];
        const options: DictionaryOption[] = types.map((vt) => ({
          label: vt.type,
          value: vt.type,
        }));
        setValuationTypeOptions(options);

        if (options.length > 0) {
          firstValuationTypeName = options[0].value;
        }
      } catch {
        setValuationTypeOptions([]);
      } finally {
        setValuationTypesLoading(false);
      }
    }

    // Step 3: Fetch scenarios and auto-select 'default' if available
    let selectedScenario: string | null = null;
    if (showScenario) {
      setScenariosLoading(true);
      try {
        const options = await loadDictionaryByName('scenarios');
        setScenarioOptions(options);

        if (options.some((opt: DictionaryOption) => opt.value === 'default')) {
          selectedScenario = 'default';
        }
      } catch {
        setScenarioOptions([]);
      } finally {
        setScenariosLoading(false);
      }
    }

    // Single onChange call with fully-resolved state — prevents parent auto-fire
    // effects from triggering with partial/intermediate values.
    onChangeRef.current({
      observationDate: latestDate,
      scenario: selectedScenario,
      valuationType: firstValuationTypeName,
    });
  }, [
    dateSelectionMode,
    allowUnavailableDateSelection,
    showValuationType,
    showScenario,
    runMode,
  ]);

  // --- Perform self-initialization on mount (only once) ---
  useEffect(() => {
    if (!value.observationDate) {
      performSelfInitialization();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run once on mount — performSelfInitialization is stable due to useCallback

  // Scenario dictionary is independent from runMode/valuationType and must be loaded
  // for every mounted instance. Sensitivity page switches filter/balance controls, so
  // relying only on self-initialization can leave the scenario Select with no options
  // when the parent already provides an observationDate.
  useEffect(() => {
    if (!showScenario || scenarioOptions.length > 0 || scenariosLoading) {
      return;
    }

    let cancelled = false;
    setScenariosLoading(true);
    loadDictionaryByName('scenarios')
      .then((options) => {
        if (!cancelled) {
          setScenarioOptions(options);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setScenarioOptions([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setScenariosLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [scenarioOptions.length, scenariosLoading, showScenario]);

  // --- Load available observation dates (after self-initialization, used for dropdown disabled dates) ---
  // NOTE: This effect runs ONLY when self-init has NOT yet fetched dates (e.g., when value.observationDate
  // is pre-populated by the parent and self-init was skipped). Once self-init completes, this effect
  // skips to avoid duplicate API calls — self-init already set availableDates.
  useEffect(() => {
    if (dateSelectionMode === 'free' && !allowUnavailableDateSelection) {
      setAvailableDates([]);
      return;
    }

    // Skip if self-initialization has already set availableDates (avoids duplicate API call)
    if (selfInitializedRef.current) return;

    let cancelled = false;
    getObservationDatesApiValuationResultsObservationDatesGet()
      .then((response) => {
        if (!cancelled) {
          const dates = response?.observation_dates || [];
          setAvailableDates(dates);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAvailableDates([]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [allowUnavailableDateSelection, dateSelectionMode]);

  // --- Load valuation types when observationDate changes (after initial mount) ---
  useEffect(() => {
    if (!shouldLoadValuationTypes(showValuationType, value.observationDate)) {
      setValuationTypeOptions([]);
      setValuationTypesLoading(false);
      return;
    }

    let cancelled = false;
    setValuationTypesLoading(true);

    getAvailableValuationTypesApiValuationResultsValuationTypesGet({
      observationDate: value.observationDate,
      runMode: runMode ?? 'simulation',
    })
      .then((response) => {
        if (!cancelled) {
          const types = (response?.valuation_types || []) as ValuationTypeInfo[];
          const options: DictionaryOption[] = types.map((vt) => ({
            label: vt.type,
            value: vt.type,
          }));
          setValuationTypeOptions(options);
          const resolvedValuationType = resolveAvailableValuationType(options, value.valuationType);
          if (resolvedValuationType !== value.valuationType) {
            onChangeRef.current({
              ...value,
              valuationType: resolvedValuationType,
            });
          }
        }
      })
      .catch(() => {
        if (!cancelled) {
          setValuationTypeOptions([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setValuationTypesLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [showValuationType, value.observationDate, runMode, value.valuationType]);

  // --- Manual change handlers ---
  // When user manually changes a field, reset the corresponding auto-selection flag
  // so that dependent fields can be re-auto-selected.
  const handleDateChange = useCallback((date: dayjs.Dayjs | null) => {
    // Reset auto-selections for dependent fields
    selfInitializedRef.current = true; // Prevent re-init
    onChange({
      observationDate: date ? date.format('YYYY-MM-DD') : '',
      scenario: value.scenario,
      valuationType: value.valuationType,
    });
  }, [value]);

  const handleScenarioChange = useCallback((scenario: string | null) => {
    onChange({
      observationDate: value.observationDate,
      scenario,
      valuationType: value.valuationType,
    });
  }, [value]);

  const handleValuationTypeChange = useCallback((valuationType: string | null) => {
    onChange({
      observationDate: value.observationDate,
      scenario: value.scenario,
      valuationType,
    });
  }, [value]);

  // --- Render ---
  const availableDateSet = new Set(
    availableDates.map((d) => dayjs(d.date).format('YYYY-MM-DD'))
  );

  const observationDateValue = value.observationDate ? dayjs(value.observationDate) : null;

  return (
    <Space wrap>
      <Typography.Text strong>{observationDateLabel}</Typography.Text>
      <DatePicker
        style={{ width: datePickerWidth }}
        placeholder="Observation date"
        value={observationDateValue}
        onChange={handleDateChange}
        status={value.observationDate ? undefined : 'error'}
        disabledDate={(current) => {
          if (dateSelectionMode === 'free' || allowUnavailableDateSelection) {
            return false;
          }
          if (availableDateSet.size === 0) {
            return false;
          }
          return !availableDateSet.has(current.format('YYYY-MM-DD'));
        }}
        cellRender={(current, info) => {
          const originNode = info.originNode;
          const currentDate = dayjs(current);
          if ((dateSelectionMode === 'free' && !allowUnavailableDateSelection) || info.type !== 'date' || !currentDate.isValid()) {
            return originNode;
          }

          if (!availableDateSet.has(currentDate.format('YYYY-MM-DD'))) {
            return originNode;
          }

          return (
            <div className="simulation-available-date-cell" title="Simulation available">
              {originNode}
            </div>
          );
        }}
      />
      {showValuationType && (
        <>
          <Typography.Text strong>{valuationTypeLabel}</Typography.Text>
          <Select
            style={{ width: valuationTypeSelectWidth }}
            placeholder="Выберите вид оценки"
            value={value.valuationType ?? undefined}
            onChange={handleValuationTypeChange}
            options={valuationTypeOptions}
            loading={valuationTypesLoading}
            allowClear
          />
        </>
      )}
      {showScenario && (
        <>
          <Typography.Text strong>{scenarioLabel}</Typography.Text>
          <Select
            style={{ width: scenarioSelectWidth }}
            placeholder="Выберите сценарий"
            value={value.scenario ?? undefined}
            onChange={handleScenarioChange}
            options={scenarioOptions}
            loading={scenariosLoading}
            allowClear
          />
        </>
      )}
    </Space>
  );
};

export default ObservationDateScenarioControl;
