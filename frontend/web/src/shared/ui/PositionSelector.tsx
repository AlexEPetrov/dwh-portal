import { getContractsListApiManagementContractsGet, getCurvesListApiManagementCurvesGet, getDatasetsListApiManagementDatasetsGet, getMonitoringReportDatesApiReportingMonitoringReportDatesGet, getMonitoringSourceDocumentApiReportingMonitoringSourceGet } from '@shared/api/generated/services.gen';
import type { ObjectInfoModel, ReportingMonitoringSourceRowItem } from '@shared/api/generated/types.gen';
import MonitoringSourceTable from '@shared/ui/MonitoringSourceTable';
import {
  createConstantUri,
  createContractUri,
  createCurveUri,
  createDatasetUri,
  createFileUri,
  createPythonUri,
  getInternalUriLabel,
  parseInternalUri
} from '@shared/utils/internal-uri';
import { Alert, Input, List, Radio, Select, Space, Typography } from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';

const { Text } = Typography;

type PositionSource = 'dataset' | 'curve' | 'contract' | 'constant' | 'file' | 'python' | 'none';

const isLegacyDatasetTupleValue = (value: string | null): boolean => {
  if (!value) return false;
  try {
    const parsedValue = JSON.parse(value);
    return Array.isArray(parsedValue) && parsedValue.length >= 4;
  } catch {
    return false;
  }
};

const decodeUriForDiagnostics = (uri: string | null | undefined): string => {
  if (!uri) return '∅';
  try {
    return decodeURIComponent(uri);
  } catch {
    try {
      return decodeURI(uri);
    } catch {
      return uri;
    }
  }
};

const getMonitoringSourceRowKey = (row: ReportingMonitoringSourceRowItem, index: number): string =>
  [
    row.value || 'no-value',
    JSON.stringify(row.raw_values || {}),
    row.page_title,
    row.subheader,
    row.entity_name,
    row.metric_name,
    row.metric_period,
    row.metric_value,
    String(index),
  ].join('::');

const formatMonitoringReportDate = (value: string): string => {
  if (/^\d{8}$/.test(value)) {
    return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`;
  }

  return value;
};

const matchesDatasetUriParams = (
  row: ReportingMonitoringSourceRowItem,
  params: Record<string, string>,
): boolean => {
  const paramEntries = Object.entries(params).filter(([, value]) => value !== '');
  if (paramEntries.length === 0) return false;

  if (row.page_title && params.page_title && row.page_title !== params.page_title) return false;
  if (row.subheader && params.subheader && row.subheader !== params.subheader) return false;
  if (row.entity_name && params.entity_name && row.entity_name !== params.entity_name) return false;
  if (row.metric_name && params.metric_name && row.metric_name !== params.metric_name) return false;
  for (const [key, expectedValue] of paramEntries) {
    if (key in (row.raw_values || {}) && row.raw_values?.[key] !== expectedValue) return false;
  }
  return true;
};

const buildDatasetUriParamsFromRow = (row: ReportingMonitoringSourceRowItem): Record<string, string> => {
  const params: Record<string, string> = {};
  if (row.page_title) params.page_title = row.page_title;
  if (row.subheader) params.subheader = row.subheader;
  if (row.entity_name) params.entity_name = row.entity_name;
  if (row.metric_name) params.metric_name = row.metric_name;
  if (row.metric_period) params.metric_period = row.metric_period;

  if (Object.keys(params).length > 0) return params;
  return Object.fromEntries(
    Object.entries(row.raw_values || {}).filter(([, value]) => value !== ''),
  );
};

export type PositionSelectorProps = {
  value: string | null;
  onChange: (value: string | null) => void;
  observationDate?: string;
  placeholder?: string;
  /** Preloaded datasets list (optional — if provided, avoids API call) */
  datasets?: ObjectInfoModel[];
  /** Preloaded curves list (optional — if provided, avoids API call) */
  curves?: ObjectInfoModel[];
};

const PositionSelector = ({
  value,
  onChange,
  observationDate,
  placeholder = 'Выберите позицию',
  datasets: externalDatasets,
  curves: externalCurves,
}: PositionSelectorProps) => {
  // ─── Parse current value ───────────────────────────────────────────────────

  const parsed = useMemo(() => parseInternalUri(value), [value]);
  const isLegacyDatasetValue = useMemo(() => isLegacyDatasetTupleValue(value), [value]);

  const [source, setSource] = useState<PositionSource>(() => {
    if (!parsed) return isLegacyDatasetValue ? 'dataset' : 'none';
    // Guard: only accept valid PositionSource values
    const src = parsed.source;
    if (src === 'dataset' || src === 'curve' || src === 'contract' || src === 'constant' || src === 'file' || src === 'python') {
      return src;
    }
    return 'none';
  });

  // ─── Dataset mode state ────────────────────────────────────────────────────

  const [datasetRows, setDatasetRows] = useState<ReportingMonitoringSourceRowItem[]>([]);
  const [datasetLoading, setDatasetLoading] = useState(false);
  const [monitoringReportDates, setMonitoringReportDates] = useState<string[]>([]);
  const [monitoringReportDatesLoading, setMonitoringReportDatesLoading] = useState(false);
  const [selectedMonitoringReportDate, setSelectedMonitoringReportDate] = useState<string | null>(null);
  const [datasetSearch, setDatasetSearch] = useState('');
  const [datasetPageTitleFilter, setDatasetPageTitleFilter] = useState<string | undefined>(undefined);
  const [datasetPage, setDatasetPage] = useState(1);
  const [datasetPageSize, setDatasetPageSize] = useState(50);
  const [datasetSelectedValue, setDatasetSelectedValue] = useState<string | null>(null);
  const [datasetSelectedRowKey, setDatasetSelectedRowKey] = useState<string | null>(null);
  /** URI params from parsed dataset:// URI — used to resolve to actual row.value after data loads */
  const [datasetUriParams, setDatasetUriParams] = useState<Record<string, string> | null>(null);
  /** Track if user has manually interacted with the table — disables prioritizeSelected after interaction */
  const [datasetUserInteracted, setDatasetUserInteracted] = useState(false);

  // ─── Dataset selector state ────────────────────────────────────────────────

  const [datasetSlug, setDatasetSlug] = useState<string | null>(null);
  const [datasetList, setDatasetList] = useState<ObjectInfoModel[]>(() => (externalDatasets ?? []) as unknown as ObjectInfoModel[]);
  const [datasetListLoading, setDatasetListLoading] = useState(false);
  const [datasetListLoaded, setDatasetListLoaded] = useState(false);

  // Auto-select dataset when only one available (for legacy values without dataset slug).
  // When the incoming value is legacy format (no dataset slug), and there's exactly one
  // dataset available, auto-select it so that row selection works correctly.
  useEffect(() => {
    if (datasetListLoaded && datasetList.length === 1 && !datasetSlug) {
      setDatasetSlug(datasetList[0].slug || null);
    }
  }, [datasetListLoaded, datasetList, datasetSlug]);

  // ─── Load datasets list ────────────────────────────────────────────────────

  useEffect(() => {
    if (datasetListLoaded) return;

    let mounted = true;

    const loadDatasets = async () => {
      setDatasetListLoading(true);
      try {
        const response = await getDatasetsListApiManagementDatasetsGet();
        if (mounted) {
          const datasets = (response ?? []) as unknown as ObjectInfoModel[];
          setDatasetList(datasets);
          setDatasetListLoaded(true);
        }
      } catch (err) {
        if (mounted) {
          setDatasetList([]);
          setDatasetListLoaded(true);
        }
      } finally {
        if (mounted) {
          setDatasetListLoading(false);
        }
      }
    };

    void loadDatasets();

    return () => {
      mounted = false;
    };
  }, [datasetListLoaded]);

  // ─── Sync datasetSlug from parsed URI ──────────────────────────────────────
  // This syncs the dataset slug from the URI to the Select component.
  // We also sync when datasetListLoaded changes to handle the case where
  // the dataset list loads after the initial render — ensures the Select
  // can match the value against the loaded options.

  const [syncedDatasetSlug, setSyncedDatasetSlug] = useState<string | null>(null);

  useEffect(() => {
    if (parsed?.source === 'dataset' && parsed.dataset) {
      setSyncedDatasetSlug(parsed.dataset);
    }
  }, [parsed]);

  // When dataset list loads, sync the slug again to ensure matching works
  useEffect(() => {
    if (datasetListLoaded && parsed?.source === 'dataset' && parsed.dataset) {
      setSyncedDatasetSlug(parsed.dataset);
    }
  }, [datasetListLoaded, parsed]);

  // Use explicit user selection first. Otherwise switching datasets keeps showing
  // the slug parsed from the previously saved URI and reloads the old row set.
  const effectiveDatasetSlug = datasetSlug ?? syncedDatasetSlug;

  // ─── Curve mode state ──────────────────────────────────────────────────────

  const [curveList, setCurveList] = useState<ObjectInfoModel[]>(() => externalCurves || []);
  const [curveListLoading, setCurveListLoading] = useState(false);
  const [curveListLoaded, setCurveListLoaded] = useState(false);
  const [selectedCurveSlug, setSelectedCurveSlug] = useState<string | null>(null);

  // ─── Contract mode state ───────────────────────────────────────────────────

  const [contractFilter, setContractFilter] = useState('');
  // Store the raw contract value to avoid losing it during typing
  const [rawContractValue, setRawContractValue] = useState<string | null>(null);

  // Contract list for selection
  const [contractList, setContractList] = useState<ObjectInfoModel[]>([]);
  const [contractListLoading, setContractListLoading] = useState(false);
  const [contractListLoaded, setContractListLoaded] = useState(false);

  // ─── Constant mode state ───────────────────────────────────────────────────

  const [constantValue, setConstantValue] = useState('');

  // ─── File (Excel source) mode state ────────────────────────────────────────

  const [filePath, setFilePath] = useState('');

  // ─── Python script mode state ──────────────────────────────────────────────

  const [pythonScript, setPythonScript] = useState('');

  // ─── Sync parsed value to local state ──────────────────────────────────────

  useEffect(() => {
    if (!parsed) {
      if (isLegacyDatasetValue) {
        setSource('dataset');
        setDatasetSelectedValue(value);
        setDatasetSelectedRowKey(null);
        setRawContractValue(null);
        setContractFilter('');
        setConstantValue('');
        setFilePath('');
        setPythonScript('');
        setSelectedCurveSlug(null);
        return;
      }

      setSource('none');
      setDatasetSelectedValue(null);
      setDatasetSelectedRowKey(null);
      setRawContractValue(null);
      setContractFilter('');
      setConstantValue('');
      setFilePath('');
      setPythonScript('');
      setSelectedCurveSlug(null);
      return;
    }

    if (parsed.source === 'file') {
      setSource('file');
      setFilePath(parsed.filePath || '');
    } else if (parsed.source === 'python') {
      setSource('python');
      setPythonScript(parsed.scriptFilename || '');
    } else if (parsed.source === 'dataset') {
      setSource('dataset');
      const params = parsed.params || null;
      setDatasetUriParams(params);
      setRawContractValue(null);
      setContractFilter('');
      setConstantValue('');
      setFilePath('');
      setPythonScript('');
      setSelectedCurveSlug(null);
    } else if (parsed.source === 'curve') {
      setSource('curve');
      setDatasetSelectedValue(null);
      setDatasetUriParams(null);
      setRawContractValue(null);
      setContractFilter('');
      setConstantValue('');
      setFilePath('');
      setPythonScript('');
      // Normalize curve slug to handle potential format variations
      const normalizedCurve = parsed.curve ? parsed.curve.trim() : null;
      setSelectedCurveSlug(normalizedCurve);
    } else if (parsed.source === 'contract') {
      setSource('contract');
      setDatasetSelectedValue(null);
      setDatasetUriParams(null);
      setConstantValue('');
      setFilePath('');
      setPythonScript('');
      setSelectedCurveSlug(null);
      // Store the raw value and extract query string as-is (preserves all keys, including unknown ones)
      setRawContractValue(parsed.raw || null);
      // Extract the query string from the raw URI
      const raw = parsed.raw || '';
      const qIndex = raw.indexOf('?');
      if (qIndex !== -1) {
        setContractFilter(raw.slice(qIndex + 1));
      } else {
        setContractFilter('');
      }
    } else if (parsed.source === 'constant') {
      setSource('constant');
      setDatasetSelectedValue(null);
      setDatasetUriParams(null);
      setRawContractValue(null);
      setContractFilter('');
      setConstantValue(parsed.constantValue || '');
      setFilePath('');
      setPythonScript('');
      setSelectedCurveSlug(null);
    }
  }, [isLegacyDatasetValue, parsed, value]);

  // ─── Load monitoring report dates ──────────────────────────────────────────

  useEffect(() => {
    if (source !== 'dataset' || !effectiveDatasetSlug) {
      setMonitoringReportDates([]);
      setSelectedMonitoringReportDate(null);
      return;
    }

    let mounted = true;

    const loadReportDates = async () => {
      setMonitoringReportDatesLoading(true);
      try {
        const response = await getMonitoringReportDatesApiReportingMonitoringReportDatesGet({
          datasetSlug: effectiveDatasetSlug,
        });

        if (!mounted) return;

        const dates = [...(response.report_dates || [])].sort();
        setMonitoringReportDates(dates);
        setSelectedMonitoringReportDate((current) => {
          if (current && dates.includes(current)) return current;
          return dates.length > 0 ? dates[dates.length - 1] : null;
        });
      } catch {
        if (mounted) {
          setMonitoringReportDates([]);
          setSelectedMonitoringReportDate(null);
        }
      } finally {
        if (mounted) {
          setMonitoringReportDatesLoading(false);
        }
      }
    };

    void loadReportDates();

    return () => {
      mounted = false;
    };
  }, [source, effectiveDatasetSlug]);

  // ─── Load monitoring source data ───────────────────────────────────────────

  useEffect(() => {
    if (source !== 'dataset') return;

    let mounted = true;

    const loadDataset = async () => {
      if ((!selectedMonitoringReportDate && !observationDate) || !effectiveDatasetSlug) return;

      setDatasetLoading(true);
      try {
        const response = await getMonitoringSourceDocumentApiReportingMonitoringSourceGet({
          datasetSlug: effectiveDatasetSlug,
          observDate: selectedMonitoringReportDate ? undefined : observationDate,
          reportDate: selectedMonitoringReportDate || undefined,
        });

        if (mounted) {
          const rows = response?.rows || [];
          setDatasetRows(rows);

        }
      } catch {
        // Ignore errors — rows will be empty
      } finally {
        if (mounted) {
          setDatasetLoading(false);
        }
      }
    };

    void loadDataset();

    return () => {
      mounted = false;
    };
  }, [source, observationDate, effectiveDatasetSlug, selectedMonitoringReportDate]);

  useEffect(() => {
    if (source !== 'dataset' || !datasetUriParams || datasetRows.length === 0) return;

    const matchedRowIndex = datasetRows.findIndex((row) => matchesDatasetUriParams(row, datasetUriParams));
    const matchedRow = matchedRowIndex >= 0 ? datasetRows[matchedRowIndex] : null;
    if (!matchedRow || !matchedRow.value) return;

    setDatasetSelectedValue(matchedRow.value);
    setDatasetSelectedRowKey(getMonitoringSourceRowKey(matchedRow, matchedRowIndex));
  }, [datasetRows, datasetUriParams, source]);

  // ─── Load curve list ───────────────────────────────────────────────────────

  useEffect(() => {
    if (source !== 'curve' || curveListLoaded) return;

    let mounted = true;

    const loadCurves = async () => {
      setCurveListLoading(true);
      try {
        const response = await getCurvesListApiManagementCurvesGet();
        if (mounted) {
          const curves = response || [];
          setCurveList(curves);
          setCurveListLoaded(true);
        }
      } catch (err) {
        if (mounted) {
          setCurveList([]);
          setCurveListLoaded(true);
        }
      } finally {
        if (mounted) {
          setCurveListLoading(false);
        }
      }
    };

    void loadCurves();

    return () => {
      mounted = false;
    };
  }, [source, curveListLoaded]);

  // ─── Load contract list ────────────────────────────────────────────────────

  useEffect(() => {
    if (source !== 'contract' || contractListLoaded) return;

    let mounted = true;

    const loadContracts = async () => {
      setContractListLoading(true);
      try {
        const xApiKey = localStorage.getItem('x_api_key') || 'dev';
        const response = await getContractsListApiManagementContractsGet({ xApiKey });
        if (mounted) {
          const contracts = response || [];
          setContractList(contracts);
          setContractListLoaded(true);
        }
      } catch (err) {
        if (mounted) {
          setContractList([]);
          setContractListLoaded(true);
        }
      } finally {
        if (mounted) {
          setContractListLoading(false);
        }
      }
    };

    void loadContracts();

    return () => {
      mounted = false;
    };
  }, [source, contractListLoaded]);

  // ─── Build URI on change ───────────────────────────────────────────────────

  const buildUri = useCallback((): string | null => {
    switch (source) {
      case 'dataset':
        // Always produce NEW format dataset:// SLUG?... URIs.
        // Never return legacy raw values — always wrap in proper dataset:// URI.
        const activeDatasetSlug = effectiveDatasetSlug;
        if (datasetSelectedValue && activeDatasetSlug) {
          const matchedRow = datasetRows.find((row) => row.value === datasetSelectedValue);
          if (matchedRow) {
            return createDatasetUri(activeDatasetSlug, buildDatasetUriParamsFromRow(matchedRow));
          }
          // Fallback: no matching row found, create minimal URI with the value
          return createDatasetUri(activeDatasetSlug, { value: datasetSelectedValue });
        }
        return null;
      case 'curve':
        return selectedCurveSlug ? createCurveUri(selectedCurveSlug) : null;
      case 'contract': {
        // Parse the filter string into params
        const params: Record<string, string> = {};
        if (contractFilter.trim()) {
          const pairs = contractFilter.split('&');
          for (const pair of pairs) {
            const eqIndex = pair.indexOf('=');
            if (eqIndex > 0) {
              const key = pair.slice(0, eqIndex).trim();
              const val = pair.slice(eqIndex + 1).trim();
              if (key && val) {
                params[key] = val;
              }
            }
          }
        }
        // If no valid params, return the raw value as-is instead of null
        // This prevents the value from disappearing while typing
        if (Object.keys(params).length === 0) {
          return rawContractValue;
        }
        return createContractUri(params);
      }
      case 'constant':
        return constantValue ? createConstantUri(constantValue) : null;
      case 'file':
        return filePath ? createFileUri(filePath) : null;
      case 'python':
        return pythonScript ? createPythonUri(pythonScript) : null;
      case 'none':
      default:
        return null;
    }
  }, [source, datasetSelectedValue, effectiveDatasetSlug, datasetRows, selectedCurveSlug, contractFilter, constantValue, rawContractValue, filePath, pythonScript]);

  const handleSourceChange = useCallback(
    (nextSource: PositionSource) => {
      // Reset selection for the source we're leaving
      if (source !== 'dataset') {
        setDatasetSelectedValue(null);
        setDatasetSelectedRowKey(null);
      }
      if (source !== 'curve') {
        setSelectedCurveSlug(null);
      }
      if (source !== 'contract') {
        setContractFilter('');
        setRawContractValue(null);
      }
      if (source !== 'constant') {
        setConstantValue('');
      }
      if (source !== 'file') {
        setFilePath('');
      }
      if (source !== 'python') {
        setPythonScript('');
      }

      // Now switch to the new source
      setSource(nextSource);

      // Only emit a URI if the new source has a valid selection.
      // Don't emit null when switching sources without a selection,
      // because that would trigger the parsed effect to switch to "none" source.
      if (nextSource === 'curve' && selectedCurveSlug) {
        onChange(createCurveUri(selectedCurveSlug));
      } else if (nextSource === 'dataset' && datasetSelectedValue) {
        // Always produce NEW format dataset:// SLUG?... URIs.
        // Never emit legacy raw values.
        const uri = buildUri();
        onChange(uri);
      } else if (nextSource === 'constant' && constantValue) {
        onChange(createConstantUri(constantValue));
      } else if (nextSource === 'contract' && rawContractValue) {
        onChange(rawContractValue);
      } else if (nextSource === 'file' && filePath) {
        onChange(createFileUri(filePath));
      } else if (nextSource === 'python' && pythonScript) {
        onChange(createPythonUri(pythonScript));
      } else if (nextSource === 'none') {
        // Explicit clear — emit null
        onChange(null);
      }
      // For other cases (e.g., switching to curve without a selection),
      // just switch the tab without emitting any value.
    },
    [source, datasetSelectedValue, selectedCurveSlug, rawContractValue, constantValue, filePath, pythonScript],
  );

  // ─── Dataset row selection ─────────────────────────────────────────────────

  const handleDatasetRowSelect = useCallback(
    (_row: ReportingMonitoringSourceRowItem | null, rowKey: string | null) => {
      setDatasetSelectedRowKey(rowKey);
      setDatasetUserInteracted(true);
    },
    [],
  );

  const handleDatasetValueSelect = useCallback(
    (nextValue: string | null) => {
      setDatasetSelectedValue(nextValue);
      setDatasetUserInteracted(true);
      // Use datasetSlug (user's explicit dropdown selection) first, falling back to
      // syncedDatasetSlug (from parsed URI). This ensures the correct dataset is used
      // when switching from another mode (e.g., contract) to dataset mode.
      const activeDatasetSlug = datasetSlug ?? syncedDatasetSlug ?? null;
      if (nextValue && activeDatasetSlug) {
        // Build a dataset:// URI using the selected dataset slug and the row's monitoring fields.
        // The row is looked up to extract page_title, subheader, entity_name, metric_name.
        const matchedRow = datasetRows.find((row) => row.value === nextValue);
        if (matchedRow) {
          const uri = createDatasetUri(activeDatasetSlug, buildDatasetUriParamsFromRow(matchedRow));
          onChange(uri);
        } else {
          // If matchedRow not found, still try to build a URI with the active slug.
          // This handles cases where the row might have been filtered or pagination changed.
          const uri = createDatasetUri(activeDatasetSlug, { value: nextValue });
          onChange(uri);
        }
      }
    },
    [onChange, datasetSlug, syncedDatasetSlug, datasetRows],
  );

  // ─── Contract filter change ────────────────────────────────────────────────

  /**
   * Parse the filter text and build a contract URI.
   * Called on blur/enter, not on every keystroke, to avoid lag.
   */
  const commitContractsFilter = useCallback(() => {
    const params: Record<string, string> = {};
    if (contractFilter.trim()) {
      const pairs = contractFilter.split('&');
      for (const pair of pairs) {
        const eqIndex = pair.indexOf('=');
        if (eqIndex > 0) {
          const key = pair.slice(0, eqIndex).trim();
          const val = pair.slice(eqIndex + 1).trim();
          if (key && val) {
            params[key] = val;
          }
        }
      }
    }
    // If no valid params, keep the raw value as-is instead of emitting null
    if (Object.keys(params).length === 0) {
      const newValue = contractFilter.trim()
        ? `contract://${contractFilter.trim()}`
        : rawContractValue;
      setRawContractValue(newValue);
      onChange(newValue ?? null);
    } else {
      const uri = createContractUri(params);
      setRawContractValue(uri);
      onChange(uri);
    }
  }, [contractFilter, rawContractValue, onChange]);

  // ─── Constant change ───────────────────────────────────────────────────────

  /**
   * Commit the constant value. Called on blur/enter, not on every keystroke.
   */
  const commitConstant = useCallback(() => {
    if (constantValue) {
      onChange(createConstantUri(constantValue));
    } else {
      onChange(null);
    }
  }, [constantValue, onChange]);

  /**
   * Commits the current file path value to the parent via createFileUri.
   */
  const commitFilePath = useCallback(() => {
    if (filePath) {
      onChange(createFileUri(filePath));
    } else {
      onChange(null);
    }
  }, [filePath, onChange]);

  /**
   * Commits the current python script filename value to the parent via createPythonUri.
   */
  const commitPythonScript = useCallback(() => {
    if (pythonScript) {
      onChange(createPythonUri(pythonScript));
    } else {
      onChange(null);
    }
  }, [pythonScript, onChange]);

  // ─── Clear ─────────────────────────────────────────────────────────────────

  const handleClear = useCallback(() => {
    setSource('none');
    setDatasetSelectedValue(null);
    setDatasetSelectedRowKey(null);
    setDatasetUriParams(null);
    setDatasetUserInteracted(false);
    setSelectedCurveSlug(null);
    setContractFilter('');
    setRawContractValue(null);
    setConstantValue('');
    setFilePath('');
    setPythonScript('');
    onChange(null);
  }, [onChange]);

  // ─── Computed values ───────────────────────────────────────────────────────

  // Use buildUri() result for display so it reflects the CURRENT mode's selection,
  // not the stale parsed value from the incoming prop (which may be from a different mode).
  const currentUriForDisplay = buildUri();
  const displayLabel = useMemo(() => {
    if (!currentUriForDisplay) return placeholder;
    const p = parseInternalUri(currentUriForDisplay);
    if (!p) return currentUriForDisplay;
    return getInternalUriLabel(p);
  }, [currentUriForDisplay, placeholder]);

  const datasetMatchedRow = useMemo(
    () => {
      if (datasetSelectedRowKey) {
        const keyedRow = datasetRows.find((row, index) => getMonitoringSourceRowKey(row, index) === datasetSelectedRowKey);
        if (keyedRow) return keyedRow;
      }
      return datasetRows.find((row) => row.value && row.value === datasetSelectedValue) || null;
    },
    [datasetRows, datasetSelectedRowKey, datasetSelectedValue],
  );

  const decodedCurrentUri = useMemo(() => decodeUriForDiagnostics(currentUriForDisplay), [currentUriForDisplay]);

  const diagnosticLines = useMemo(() => {
    const lines = [`source: ${source}`, `current: ${decodedCurrentUri}`];

    if (source === 'dataset' && datasetMatchedRow) {
      lines.push(
        `selected row: ${[
          datasetMatchedRow.page_title,
          datasetMatchedRow.subheader,
          datasetMatchedRow.entity_name,
          datasetMatchedRow.metric_name,
          datasetMatchedRow.metric_period,
        ].filter(Boolean).join(' / ')}`,
      );
    }

    return lines;
  }, [datasetMatchedRow, decodedCurrentUri, source]);

  // ─── Render ────────────────────────────────────────────────────────────────

  // Build the current URI from the active mode's state — this is what will be applied
  // when the user confirms. Using buildUri() is correct because it reads the current
  // mode's own fields (datasetSelectedValue, selectedCurveSlug, etc.), not the incoming
  // value prop which may belong to a different mode.
  const currentBuildUri = buildUri();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ flex: 1, overflow: 'hidden', paddingBottom: 16, minHeight: 0 }}>
        <div style={{ width: '100%', height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Source selector */}
          <Space direction="vertical" size={8} style={{ width: '100%', flexShrink: 0 }}>
            <Text strong>Источник:</Text>
            <Radio.Group
              value={source}
              onChange={(e) => handleSourceChange(e.target.value)}
              buttonStyle="solid"
            >
              <Radio.Button value="dataset">Dataset</Radio.Button>
              <Radio.Button value="curve">Curve</Radio.Button>
              <Radio.Button value="contract">Contract</Radio.Button>
              <Radio.Button value="constant">Constant</Radio.Button>
              <Radio.Button value="file">Excel file</Radio.Button>
              <Radio.Button value="python">Python script</Radio.Button>
              <Radio.Button value="none">NONE</Radio.Button>
            </Radio.Group>
          </Space>

          {/* Dataset mode */}
          {source === 'dataset' && (
            <div style={{ width: '100%', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
              {/* Dataset selector */}
              <Space direction="vertical" size={4} style={{ width: '100%', flexShrink: 0 }}>
                <Text type="secondary">Источник данных:</Text>
                <Select
                  value={effectiveDatasetSlug || undefined}
                  onChange={(val) => {
                    setDatasetSlug(val ?? null);
                    setSyncedDatasetSlug(null);
                    setDatasetSelectedValue(null);
                    setDatasetSelectedRowKey(null);
                    setDatasetUriParams(null);
                    setDatasetUserInteracted(false);
                    setDatasetSearch('');
                    setDatasetPageTitleFilter(undefined);
                    setDatasetPage(1);
                    setMonitoringReportDates([]);
                    setSelectedMonitoringReportDate(null);
                    // Reset rows — they'll be reloaded based on new dataset + observation date
                    setDatasetRows([]);
                  }}
                  placeholder="Выберите датасет"
                  loading={datasetListLoading}
                  showSearch
                  filterOption={(input, option) =>
                    ((option?.label ?? '').toString().toLowerCase().includes(input.toLowerCase()) ?? false)
                  }
                  options={datasetList.map((d) => ({
                    label: `${d.name || d.slug || ''} (${d.slug || ''})`,
                    value: d.slug || '',
                  }))}
                  style={{ width: '100%' }}
                  allowClear
                />
              </Space>
              <Space direction="vertical" size={4} style={{ width: '100%', flexShrink: 0 }}>
                <Text type="secondary">Дата preview value:</Text>
                <Select
                  value={selectedMonitoringReportDate || undefined}
                  onChange={(value) => {
                    setSelectedMonitoringReportDate(value ?? null);
                    setDatasetRows([]);
                    setDatasetSearch('');
                    setDatasetPageTitleFilter(undefined);
                    setDatasetPage(1);
                  }}
                  placeholder="Выберите дату monitoring preview"
                  loading={monitoringReportDatesLoading}
                  options={monitoringReportDates.map((date) => ({
                    label: formatMonitoringReportDate(date),
                    value: date,
                  }))}
                  style={{ width: 260 }}
                  disabled={!effectiveDatasetSlug || monitoringReportDates.length === 0}
                />
                <Text type="secondary" style={{ fontSize: 11 }}>
                  Выберите позицию из monitoring source (preview date: {selectedMonitoringReportDate ? formatMonitoringReportDate(selectedMonitoringReportDate) : observationDate || '—'})
                </Text>
              </Space>
              <MonitoringSourceTable
                rows={datasetRows}
                loading={datasetLoading}
                search={datasetSearch}
                onSearchChange={(value) => {
                  setDatasetSearch(value);
                  setDatasetPage(1);
                }}
                pageTitleFilter={datasetPageTitleFilter}
                onPageTitleFilterChange={(value) => {
                  setDatasetPageTitleFilter(value);
                  setDatasetPage(1);
                }}
                page={datasetPage}
                pageSize={datasetPageSize}
                onPageChange={(page, pageSize) => {
                  setDatasetPage(page);
                  setDatasetPageSize(pageSize);
                }}
                selectedValue={datasetSelectedValue}
                selectedRowKey={datasetSelectedRowKey}
                // Only prioritize selected row during initial load (before user interaction).
                // After user clicks/selects, disable prioritization to keep list order stable.
                prioritizeSelected={!datasetUserInteracted}
                onSelectRow={handleDatasetRowSelect}
                onSelectValue={handleDatasetValueSelect}
                scrollY="auto"
                emptyText="Нет данных. Укажите observation date."
              />
            </div>
          )}

          {/* Curve mode — curve selector */}
          {source === 'curve' && (
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <Text type="secondary">
                Выберите кривую из списка
              </Text>
              <Select
                value={selectedCurveSlug || undefined}
                onChange={(val) => {
                  setSelectedCurveSlug(val ?? null);
                  if (val) {
                    onChange(createCurveUri(val));
                  }
                }}
                placeholder="Выберите кривую"
                loading={curveListLoading}
                showSearch
                filterOption={(input, option) =>
                  ((option?.label ?? '').toString().toLowerCase().includes(input.toLowerCase()) ?? false)
                }
                options={curveList.map((c) => ({
                  label: `${c.name || c.slug || ''} (${c.slug || ''})`,
                  value: c.slug || '',
                }))}
                style={{ width: '100%' }}
                allowClear
              />
            </Space>
          )}

          {/* Contract mode — filter + contract list */}
          {source === 'contract' && (
            <div style={{ width: '100%', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <Text type="secondary">
                Введите фильтр для контрактов в формате key=value&key2=value2 или выберите из списка
              </Text>
              <Input
                value={contractFilter}
                onChange={(e) => setContractFilter(e.target.value)}
                onBlur={commitContractsFilter}
                onPressEnter={commitContractsFilter}
                placeholder="gl_account=GL_TAX_1&slug=CONTRACT_1"
              />
              <Text type="secondary" style={{ fontSize: 11 }}>
                Поддерживаемые ключи: gl_account, slug, counterparty, product, delivery_market
              </Text>
              <div style={{ flex: 1, minHeight: 0, overflow: 'auto', border: '1px solid #f0f0f0', borderRadius: 4 }}>
                <List
                  size="small"
                  loading={contractListLoading}
                  dataSource={contractList.filter((c) => {
                    if (!contractFilter.trim()) return true;
                    // Extract values from filter (e.g., "slug=CONTRACT_1&gl_account=GL_1" → ["contract_1", "gl_1"])
                    const filterValues = contractFilter
                      .split('&')
                      .map((pair) => {
                        const eqIndex = pair.indexOf('=');
                        return eqIndex > 0 ? pair.slice(eqIndex + 1).trim().toLowerCase() : '';
                      })
                      .filter(Boolean);
                    const contractSlug = (c.slug || '').toLowerCase();
                    const contractName = (c.name || '').toLowerCase();
                    // Match if any filter value is found in slug or name
                    return filterValues.some((val) =>
                      contractSlug.includes(val) || contractName.includes(val)
                    );
                  })}
                  renderItem={(item) => (
                    <List.Item
                      style={{ cursor: 'pointer', padding: '4px 16px' }}
                      onClick={() => {
                        if (item.slug) {
                          const newFilter = `slug=${item.slug}`;
                          setContractFilter(newFilter);
                          const uri = createContractUri({ slug: item.slug });
                          setRawContractValue(uri);
                          onChange(uri);
                        }
                      }}
                    >
                      <List.Item.Meta
                        title={item.name || item.slug || ''}
                        description={item.slug || ''}
                      />
                    </List.Item>
                  )}
                  locale={{ emptyText: contractListLoading ? 'Загрузка...' : 'Нет доступных контрактов' }}
                />
              </div>
            </div>
          )}

          {/* Constant mode */}
          {source === 'constant' && (
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <Text type="secondary">Введите константное значение</Text>
              <Input
                value={constantValue}
                onChange={(e) => setConstantValue(e.target.value)}
                onBlur={commitConstant}
                onPressEnter={commitConstant}
                placeholder="Например: 12345.67"
              />
            </Space>
          )}

          {/* File (Excel source) mode */}
          {source === 'file' && (
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <Text type="secondary">
                Введите ссылку на Excel-источник в формате filename.xlsx!Sheet!A1:B10
              </Text>
              <Input
                value={filePath}
                onChange={(e) => setFilePath(e.target.value)}
                onBlur={commitFilePath}
                onPressEnter={commitFilePath}
                placeholder="balance.xlsx!Sheet1!A1:B10"
              />
            </Space>
          )}

          {/* Python script mode */}
          {source === 'python' && (
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <Text type="secondary">
                Введите имя Python-скрипта в директории APP_LOC_DOCUMENTS (например: calculate_balance.py)
              </Text>
              <Input
                value={pythonScript}
                onChange={(e) => setPythonScript(e.target.value)}
                onBlur={commitPythonScript}
                onPressEnter={commitPythonScript}
                placeholder="calculate_balance.py"
              />
            </Space>
          )}
        </div>
      </div>

      {/* Fixed bottom bar: current value + diagnostics */}
      <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 12, flexShrink: 0, background: '#fff', position: 'relative', zIndex: 1 }}>
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          {/* Current value display + clear */}
          <Space style={{ width: '100%', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>
                Текущее значение (будет сохранено):
              </Text>
              <Text code style={{ fontSize: 12, maxWidth: '80%', overflow: 'hidden', textOverflow: 'ellipsis', display: 'inline-block', verticalAlign: 'top' }}>
                {currentBuildUri ? displayLabel : '—'}
              </Text>
            </div>
            <a onClick={handleClear} style={{ flexShrink: 0 }}>
              Очистить
            </a>
          </Space>

          {/* Diagnostics — always visible */}
          <Alert
            type={currentBuildUri ? 'info' : 'warning'}
            showIcon
            message={currentBuildUri ? 'Текущий выбор' : 'Нет выбранного значения'}
            description={(
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 11, maxHeight: 56, overflow: 'auto' }}>
                {diagnosticLines.join('\n')}
              </pre>
            )}
          />
        </Space>
      </div>
    </div>
  );
};

export default PositionSelector;
