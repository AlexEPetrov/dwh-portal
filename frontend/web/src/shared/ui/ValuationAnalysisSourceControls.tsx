import { SearchOutlined } from '@ant-design/icons';
import { getAvailableValuationTypesApiValuationResultsValuationTypesGet, getGlTreesListApiManagementGlTreesGet, getSavedMetadataApiValuationGlCalculatedTreeSavedMetadataGet } from '@shared/api/generated/services.gen';
import type { BalanceTreeSaveMetadata, GlTreeModel_Output } from '@shared/api/generated/types.gen';
import ObservationDateScenarioControl from '@shared/ui/ObservationDateScenarioControl';
import SimulationCurrencyTargetSelector, { buildSimulationPeriodModeUpdate } from '@shared/ui/SimulationCurrencyTargetSelector';
import ValuationFilterRulesEditor from '@shared/ui/ValuationFilterRulesEditor';
import ValuationScopeFilter from '@shared/ui/ValuationScopeFilter';
import { BALANCE_NOT_SAVED_WARNING, ensureSavedBalanceAvailable } from '@shared/valuation-analysis/balanceGuard';
import type { ValuationFilterRule } from '@shared/valuation-analysis/sourceMode';
import { BALANCE_SOURCE_NOTICE, type ValuationAnalysisSourceMode, type ValuationAnalysisSourceState } from '@shared/valuation-analysis/sourceMode';
import { Alert, Button, Radio, Select, Space, Typography, message } from 'antd';
import React, { useEffect, useRef, useState } from 'react';

interface ValuationAnalysisSourceControlsProps {
  modeLabel: string;
  state: ValuationAnalysisSourceState;
  updateState: (update: Partial<ValuationAnalysisSourceState>) => void;
  periodOptions: { value: ValuationAnalysisSourceState['periodMode']; label: string }[];
  onApply: () => void;
  loading?: boolean;
  applyLabel?: string;
  showCurrencyTarget?: boolean;
  topExtra?: React.ReactNode;
  balanceTreeSelectionMode?: 'manual' | 'metadata';
  balanceMetadataSelectorMode?: 'savedBalance' | 'none';
  showBalanceValuationType?: boolean;
  balanceMetadataInfo?: React.ReactNode;
  balanceGuardObservationDates?: string[];
  showSourceModeSelector?: boolean;
  showPeriodModeSelector?: boolean;
  extraFilterActions?: React.ReactNode;
}

const ValuationAnalysisSourceControls: React.FC<ValuationAnalysisSourceControlsProps> = ({
  modeLabel,
  state,
  updateState,
  periodOptions,
  onApply,
  loading = false,
  applyLabel = 'Применить',
  showCurrencyTarget = true,
  topExtra,
  balanceTreeSelectionMode = 'manual',
  balanceMetadataSelectorMode = 'savedBalance',
  showBalanceValuationType = false,
  balanceMetadataInfo,
  balanceGuardObservationDates,
  showSourceModeSelector = true,
  showPeriodModeSelector = true,
  extraFilterActions,
}) => {
  const [trees, setTrees] = useState<GlTreeModel_Output[]>([]);
  const [treesLoading, setTreesLoading] = useState(false);
  const [treesError, setTreesError] = useState<string | null>(null);

  // Metadata coverage fetch (for balance mode)
  const [savedBalanceItems, setSavedBalanceItems] = useState<BalanceTreeSaveMetadata[]>([]);
  const [selectedBalanceMetadataKey, setSelectedBalanceMetadataKey] = useState<string | undefined>(undefined);
  const [, setMetadataLoading] = useState(false);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [showAutoResolveAlert, setShowAutoResolveAlert] = useState(false);
  const [showAdvancedRules, setShowAdvancedRules] = useState(false);
  const [balanceGuardChecking, setBalanceGuardChecking] = useState(false);
  const hasUserSelectedTree = useRef(false);

  useEffect(() => {
    let cancelled = false;

    const loadTrees = async () => {
      setTreesLoading(true);
      setTreesError(null);
      try {
        const response = await getGlTreesListApiManagementGlTreesGet();
        if (!cancelled) {
          setTrees(response || []);
        }
      } catch (error: any) {
        if (!cancelled) {
          setTreesError(error?.body?.detail || error?.message || 'Не удалось загрузить деревья баланса');
        }
      } finally {
        if (!cancelled) {
          setTreesLoading(false);
        }
      }
    };

    loadTrees();

    return () => {
      cancelled = true;
    };
  }, []);

  const isMetadataBalanceTreeSelection = balanceTreeSelectionMode === 'metadata';
  const showSavedBalanceSelector = isMetadataBalanceTreeSelection && balanceMetadataSelectorMode === 'savedBalance';
  const shouldShowPeriodModeSelector = state.sourceMode === 'filter' && showPeriodModeSelector;

  const buildBalanceMetadataKey = (item: BalanceTreeSaveMetadata) => `${item.balance_tree_slug}|${item.valuation_type}|${item.valuation_year}`;

  const sortSavedBalanceItems = (items: BalanceTreeSaveMetadata[]) => [...items].sort((left, right) => {
    const yearDiff = right.valuation_year - left.valuation_year;
    if (yearDiff !== 0) return yearDiff;
    return String(right.saved_at).localeCompare(String(left.saved_at));
  });

  const loadSavedBalanceItems = async (observationDate: string) => {
    const valuationTypesResponse = await getAvailableValuationTypesApiValuationResultsValuationTypesGet({
      observationDate,
      runMode: 'static',
    });
    const valuationTypes = (valuationTypesResponse?.valuation_types || [])
      .map((item) => item.type)
      .filter(Boolean);

    const coverageResponses = await Promise.all(valuationTypes.map((valuationType) => (
      getSavedMetadataApiValuationGlCalculatedTreeSavedMetadataGet({
        observationDate,
        valuationType,
      })
    )));

    return sortSavedBalanceItems(coverageResponses.flatMap((item) => item?.items || []));
  };

  const selectSavedBalanceMetadata = (item: BalanceTreeSaveMetadata) => {
    hasUserSelectedTree.current = true;
    setSelectedBalanceMetadataKey(buildBalanceMetadataKey(item));
    updateState({
      selectedTreeSlug: item.balance_tree_slug,
      balanceDateScenario: {
        ...state.balanceDateScenario,
        valuationType: item.valuation_type,
      },
    });
  };

  // Fetch metadata coverage for balance mode
  useEffect(() => {
    if (state.sourceMode !== 'balance' || !state.balanceDateScenario?.observationDate) return;

    let cancelled = false;

    const fetchMetadata = async () => {
      setMetadataLoading(true);
      setMetadataError(null);
      try {
        const items = showSavedBalanceSelector
          ? await loadSavedBalanceItems(state.balanceDateScenario.observationDate)
          : [];
        const response = await getSavedMetadataApiValuationGlCalculatedTreeSavedMetadataGet({
          observationDate: state.balanceDateScenario.observationDate,
          valuationType: state.balanceDateScenario.valuationType || undefined,
        });
        if (!cancelled) {
          setSavedBalanceItems(items);

          if (showSavedBalanceSelector) {
            const current = items.find((item) => (
              item.balance_tree_slug === state.selectedTreeSlug
              && item.valuation_type === state.balanceDateScenario.valuationType
            ));
            const selected = current || items[0];
            if (selected) {
              setSelectedBalanceMetadataKey(buildBalanceMetadataKey(selected));
              if (!current) {
                updateState({
                  selectedTreeSlug: selected.balance_tree_slug,
                  balanceDateScenario: {
                    ...state.balanceDateScenario,
                    valuationType: selected.valuation_type,
                  },
                });
              }
            } else {
              setSelectedBalanceMetadataKey(undefined);
              updateState({ selectedTreeSlug: undefined });
            }
          } else if (!hasUserSelectedTree.current && !state.selectedTreeSlug && response?.items?.[0]?.balance_tree_slug) {
            // Smart auto-resolve: only if user hasn't selected and no tree is currently selected
            const resolved = sortSavedBalanceItems(response.items)[0];
            updateState({
              selectedTreeSlug: resolved.balance_tree_slug,
              balanceDateScenario: {
                ...state.balanceDateScenario,
                valuationType: resolved.valuation_type,
              },
            });
            hasUserSelectedTree.current = true;
            setShowAutoResolveAlert(true);
          }
        }
      } catch (error: any) {
        if (!cancelled) {
          setMetadataError(error?.body?.detail || error?.message || 'Не удалось загрузить метаданные баланса');
        }
      } finally {
        if (!cancelled) {
          setMetadataLoading(false);
        }
      }
    };

    fetchMetadata();

    return () => {
      cancelled = true;
    };
  }, [
    state.sourceMode,
    state.balanceDateScenario?.observationDate,
    state.balanceDateScenario?.valuationType,
    state.selectedTreeSlug,
    showSavedBalanceSelector,
  ]);

  const showMissingBalanceWarning = (missingDates: string[]) => {
    void message.info(
      missingDates.length > 1
        ? `${BALANCE_NOT_SAVED_WARNING}: ${missingDates.join(', ')}`
        : BALANCE_NOT_SAVED_WARNING,
    );
  };

  const hasSavedBalanceForDates = async (observationDates: string[]) => {
    const dates = observationDates.filter(Boolean);
    if (dates.length === 0) return true;
    setBalanceGuardChecking(true);
    try {
      if (showSavedBalanceSelector) {
        const checks = await Promise.all(dates.map(async (date) => ({
          date,
          items: date === state.balanceDateScenario?.observationDate && savedBalanceItems.length > 0
            ? savedBalanceItems
            : await loadSavedBalanceItems(date),
        })));
        const missingDates = checks.filter((item) => item.items.length === 0).map((item) => item.date);
        if (missingDates.length > 0) {
          showMissingBalanceWarning(missingDates);
          return false;
        }
        if (dates.length === 1 && dates[0] === state.balanceDateScenario?.observationDate && !selectedBalanceMetadataKey) {
          void message.info('Выберите сохранённый баланс');
          return false;
        }
        return true;
      }

      const result = await ensureSavedBalanceAvailable(dates, state.balanceDateScenario?.valuationType);
      if (!result.ok) {
        showMissingBalanceWarning(result.missingDates);
        return false;
      }
      return true;
    } catch (error: any) {
      void message.error(error?.body?.detail || error?.message || 'Не удалось проверить наличие сохранённого баланса');
      return false;
    } finally {
      setBalanceGuardChecking(false);
    }
  };

  const handleModeChange = async (sourceMode: ValuationAnalysisSourceMode) => {
    if (sourceMode === 'balance') {
      const candidateDate = state.balanceDateScenario?.observationDate;
      if (candidateDate && !(await hasSavedBalanceForDates([candidateDate]))) return;
    }
    updateState({ sourceMode });
  };

  const handleBalanceDateScenarioChange = async (balanceDateScenario: ValuationAnalysisSourceState['balanceDateScenario']) => {
    const previousDate = state.balanceDateScenario?.observationDate;
    const nextDate = balanceDateScenario.observationDate;
    if (nextDate && nextDate !== previousDate && showSavedBalanceSelector) {
      setBalanceGuardChecking(true);
      try {
        const items = await loadSavedBalanceItems(nextDate);
        if (items.length === 0) {
          showMissingBalanceWarning([nextDate]);
          return;
        }
        const selected = items[0];
        setSavedBalanceItems(items);
        setSelectedBalanceMetadataKey(buildBalanceMetadataKey(selected));
        updateState({
          selectedTreeSlug: selected.balance_tree_slug,
          balanceDateScenario: {
            ...balanceDateScenario,
            valuationType: selected.valuation_type,
          },
        });
        return;
      } catch (error: any) {
        void message.error(error?.body?.detail || error?.message || 'Не удалось проверить наличие сохранённого баланса');
        return;
      } finally {
        setBalanceGuardChecking(false);
      }
    }
    if (nextDate && nextDate !== previousDate && !(await hasSavedBalanceForDates([nextDate]))) return;
    updateState({ balanceDateScenario });
  };

  const handleTreeSelectChange = (selectedTreeSlug: string | null) => {
    hasUserSelectedTree.current = true;
    updateState({ selectedTreeSlug: selectedTreeSlug || undefined });
  };

  const handleSavedBalanceSelectChange = (metadataKey: string | null) => {
    const item = savedBalanceItems.find((candidate) => buildBalanceMetadataKey(candidate) === metadataKey);
    if (!item) {
      setSelectedBalanceMetadataKey(undefined);
      updateState({ selectedTreeSlug: undefined });
      return;
    }
    selectSavedBalanceMetadata(item);
  };

  const handleApplyClick = async () => {
    if (state.sourceMode !== 'balance') {
      onApply();
      return;
    }

    const observationDates = balanceGuardObservationDates?.length
      ? balanceGuardObservationDates
      : state.balanceDateScenario?.observationDate
        ? [state.balanceDateScenario.observationDate]
        : [];
    if (observationDates.length === 0) {
      onApply();
      return;
    }

    if (!(await hasSavedBalanceForDates(observationDates))) return;
    onApply();
  };

  const treeOptions = trees
    .map((tree) => ({
      value: tree.slug || tree.name,
      label: tree.name || tree.slug || 'Без названия',
    }))
    .filter((option) => Boolean(option.value));

  const savedBalanceOptions = savedBalanceItems.map((item) => ({
    value: buildBalanceMetadataKey(item),
    label: `${item.balance_tree_name || item.balance_tree_slug} — ${item.valuation_type} — год ${item.valuation_year}`,
  }));

  return (
    <>
      <div style={{ marginBottom: 12 }}>
        <div style={{ width: '100%', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
          <Space wrap style={{ flex: 1, minWidth: 0, alignItems: 'center' }}>
            <Typography.Text strong>{modeLabel}</Typography.Text>
            {showSourceModeSelector && (
              <Radio.Group value={state.sourceMode} onChange={(event) => void handleModeChange(event.target.value)} buttonStyle="solid">
                <Radio.Button value="filter">По фильтрам (только симуляции)</Radio.Button>
                <Radio.Button value="balance">По балансу</Radio.Button>
              </Radio.Group>
            )}
            {state.sourceMode === 'balance' && !isMetadataBalanceTreeSelection && (
              <Select
                style={{ width: 260 }}
                placeholder="Дерево баланса"
                value={state.selectedTreeSlug}
                onChange={handleTreeSelectChange}
                options={treeOptions}
                loading={treesLoading}
                allowClear
                showSearch
                optionFilterProp="label"
              />
            )}
            {state.sourceMode === 'balance' && <Typography.Text type="secondary">{BALANCE_SOURCE_NOTICE}</Typography.Text>}
          </Space>
          {topExtra && <div style={{ flexShrink: 0, marginLeft: 'auto' }}>{topExtra}</div>}
        </div>
        {treesError && state.sourceMode === 'balance' && (
          <Alert
            message="Ошибка загрузки деревьев баланса"
            description={treesError}
            type="error"
            showIcon
            style={{ marginTop: 8 }}
          />
        )}
        {state.sourceMode === 'filter' && (
          <Space wrap style={{ marginTop: 8 }}>
            <ObservationDateScenarioControl
              value={state.dateScenario}
              onChange={(dateScenario) => updateState({ dateScenario })}
              runMode="simulation"
            />
            {shouldShowPeriodModeSelector && (
              <>
                <Typography.Text strong>Period mode:</Typography.Text>
                <Select
                  style={{ width: 150 }}
                  value={state.periodMode}
                  onChange={(periodMode) => updateState(buildSimulationPeriodModeUpdate(state.target, periodMode))}
                  options={periodOptions}
                />
              </>
            )}
            {showCurrencyTarget && (
              <SimulationCurrencyTargetSelector
                value={state.target}
                periodMode={state.periodMode}
                onChange={(target) => updateState({ target })}
              />
            )}
          </Space>
        )}
      </div>

      {state.sourceMode === 'filter' ? (
        <>
          <ValuationScopeFilter
            value={state.scopeFilter}
            onChange={(scopeFilter) => updateState({ scopeFilter })}
            onPresetObservationDateChange={(observationDate) => updateState({ dateScenario: { ...state.dateScenario, observationDate } })}
            onPresetPeriodModeChange={(periodMode) => updateState({ periodMode })}
            onApply={onApply}
            loading={loading}
            applyLabel={applyLabel}
          />
          <Button type="link" onClick={() => setShowAdvancedRules((shown) => !shown)}>
            {showAdvancedRules ? 'Hide advanced rules' : 'Advanced include/exclude rules'}
          </Button>
          {showAdvancedRules && (
            <ValuationFilterRulesEditor
              value={state.filterRules || []}
              onChange={(filterRules: ValuationFilterRule[]) => updateState({ filterRules })}
            />
          )}
          {extraFilterActions}
        </>
      ) : (
        <Space direction="vertical" style={{ width: '100%', marginBottom: 12 }}>
          <Space wrap>
            <ObservationDateScenarioControl
              value={state.balanceDateScenario}
              onChange={(balanceDateScenario) => void handleBalanceDateScenarioChange(balanceDateScenario)}
              runMode="deterministic"
              showValuationType={!isMetadataBalanceTreeSelection || showBalanceValuationType}
            />
            {showSavedBalanceSelector && (
              <>
                <Typography.Text strong>Сохранённый баланс:</Typography.Text>
                <Select
                  style={{ width: 420 }}
                  placeholder="Выберите сохранённый баланс"
                  value={selectedBalanceMetadataKey}
                  onChange={handleSavedBalanceSelectChange}
                  options={savedBalanceOptions}
                  loading={balanceGuardChecking}
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  disabled={savedBalanceItems.length === 0}
                />
              </>
            )}
            <Button
              type="primary"
              icon={<SearchOutlined />}
              onClick={() => void handleApplyClick()}
              loading={loading || balanceGuardChecking}
            >
              {applyLabel}
            </Button>
          </Space>
          <Button type="link" onClick={() => setShowAdvancedRules((shown) => !shown)}>
            {showAdvancedRules ? 'Hide advanced rules' : 'Advanced include/exclude rules'}
          </Button>
          {showAdvancedRules && (
            <ValuationFilterRulesEditor
              value={state.filterRules || []}
              onChange={(filterRules: ValuationFilterRule[]) => updateState({ filterRules })}
            />
          )}
          {balanceMetadataInfo}
          {showAutoResolveAlert && !isMetadataBalanceTreeSelection && (
            <Alert
              message="Дерево выбрано автоматически"
              description="Дерево выбрано автоматически на основе последнего сохранённого баланса для текущей даты наблюдения. Вы можете изменить его вручную."
              type="info"
              showIcon
              closable
              onClose={() => setShowAutoResolveAlert(false)}
            />
          )}
          {metadataError && (
            <Alert
              message="Ошибка загрузки метаданных"
              description={metadataError}
              type="error"
              showIcon
              closable
            />
          )}
        </Space>
      )}
    </>
  );
};

export default ValuationAnalysisSourceControls;
