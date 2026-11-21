import type { AssetListItem, FreshnessItem } from '@shared/api/generated';
import {
  FilterChipGroup,
  FilterClear,
  FilterSep,
  FilterToolbar,
  FreshnessBar,
  formatBytes,
  formatDateTime,
  formatRows,
} from '@shared/ui/portal';
import { Alert, Button, Input, Select, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { readCatalogFilters, updateCatalogFilters, type CatalogFilters } from '../navigation';
import { useCatalogAssets } from '../queries';

const TYPE_TOGGLES = [
  { key: 'DATA_SOURCE', label: 'Источник' },
  { key: 'EXTRACTION_SOURCE', label: 'Извлечение' },
  { key: 'PROCESS', label: 'Loader' },
  { key: 'STORAGE_LOCATION', label: 'Хранение' },
  { key: 'TABLE', label: 'Table' },
  { key: 'VIEW', label: 'View' },
  { key: 'MATERIALIZED_VIEW', label: 'Materialized view' },
  { key: 'DATABASE', label: 'База данных' },
  { key: 'SCHEMA', label: 'Схема' },
] as const;

const PAGE_SIZE_OPTIONS = ['10', '25', '50', '100'] as const;

type ObjectsGridProps = {
  filters: CatalogFilters;
  onFreshness: (items: FreshnessItem[]) => void;
};

// Query notifications and pagination only render this subtree, never the search controls.
const ObjectsGrid = memo(({ filters, onFreshness }: ObjectsGridProps) => {
  const navigate = useNavigate();
  const filterKey = JSON.stringify(filters);
  const [pagination, setPagination] = useState({ filterKey, page: 1, pageSize: 25 });
  // A new filter starts at page one immediately, without an obsolete-page request.
  if (pagination.filterKey !== filterKey) {
    setPagination({ ...pagination, filterKey, page: 1 });
  }
  const page = pagination.filterKey === filterKey ? pagination.page : 1;
  const pageSize = pagination.pageSize;
  const assetsQuery = useCatalogAssets({
    ...filters,
    status: filters.status ?? 'active',
    page,
    pageSize,
    q: filters.q || undefined,
  });

  const items = assetsQuery.data?.items ?? [];
  const total = assetsQuery.data?.total ?? 0;
  const freshness = assetsQuery.data?.collector_freshness;

  useEffect(() => {
    // Keep the last confirmed snapshot metadata while a new result is pending.
    if (freshness) onFreshness(freshness);
  }, [freshness, onFreshness]);

  const columns: ColumnsType<AssetListItem> = useMemo(
    () => [
      {
        title: 'Объект',
        dataIndex: 'display_name',
        render: (value, row) => value || row.name || row.qualified_name,
      },
      {
        title: 'Описание',
        dataIndex: 'description',
        ellipsis: true,
        render: (value) => value || '—',
      },
      {
        title: 'Тип',
        dataIndex: 'asset_type',
        width: 170,
        render: (value) => <Tag>{value}</Tag>,
      },
      {
        title: 'Исходный файл',
        dataIndex: 'source_files',
        ellipsis: true,
        render: (value: string[] | undefined) => (value && value.length > 0 ? value.join(', ') : '—'),
      },
      {
        title: 'Размер',
        dataIndex: ['metrics', 'total_bytes'],
        render: (value) => formatBytes(value),
        width: 120,
      },
      {
        title: 'Строки',
        dataIndex: ['metrics', 'row_estimate'],
        render: (value) => formatRows(value),
        width: 120,
      },
      {
        title: 'Изменён',
        dataIndex: 'last_changed_at',
        render: (value) => formatDateTime(value),
        width: 180,
      },
      {
        title: 'Действия',
        key: 'actions',
        width: 220,
        render: (_, row) => (
          <Space size={4} onClick={(event) => event.stopPropagation()}>
            <Button size="small" type="link" onClick={() => navigate(`/objects/${row.id}`)}>
              Карточка
            </Button>
            <Button size="small" type="link" onClick={() => navigate(`/lineage/${row.id}`)}>
              Lineage
            </Button>
          </Space>
        ),
      },
    ],
    [navigate]
  );

  return (
    <div aria-busy={assetsQuery.isFetching}>
      {assetsQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message="Не удалось загрузить список объектов"
          description={assetsQuery.error instanceof Error ? assetsQuery.error.message : undefined}
        />
      ) : null}
      <Table
        rowKey="id"
        loading={assetsQuery.isPending || assetsQuery.isFetching}
        locale={{ emptyText: assetsQuery.isError ? 'Список недоступен' : assetsQuery.isPending ? 'Загрузка…' : 'Нет объектов' }}
        columns={columns}
        dataSource={items}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          pageSizeOptions: [...PAGE_SIZE_OPTIONS],
          onChange: (nextPage, nextSize) => {
            setPagination({ filterKey, page: nextPage, pageSize: nextSize });
          },
        }}
        onRow={(row) => ({
          onClick: () => navigate(`/objects/${row.id}`),
          style: { cursor: 'pointer' },
        })}
      />
    </div>
  );
});

const ObjectsHeader = memo(({ freshness }: { freshness: FreshnessItem[] }) => (
  <div>
    <Typography.Title level={2} style={{ marginBottom: 4 }}>
          Все объекты
    </Typography.Title>
    <FreshnessBar items={freshness} />
  </div>
));

const ObjectsPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(() => readCatalogFilters(searchParams), [searchParams]);
  const selectedTypes = useMemo(() => filters.type?.split(',').filter(Boolean) ?? [], [filters.type]);
  const q = filters.q ?? '';
  const [searchDraft, setSearchDraft] = useState(q);
  const status = filters.status ?? 'active';
  const [freshness, setFreshness] = useState<FreshnessItem[]>([]);
  const onFreshness = useCallback((items: FreshnessItem[]) => {
    setFreshness((current) => JSON.stringify(current) === JSON.stringify(items) ? current : items);
  }, []);

  const updateFilters = (updates: Partial<CatalogFilters>) => {
    if ('q' in updates) setSearchDraft(updates.q ?? '');
    setSearchParams((current) => updateCatalogFilters(current, { q: searchDraft, ...updates }), { replace: true });
  };

  useEffect(() => {
    setSearchDraft(q);
  }, [q]);

  useEffect(() => {
    if (searchDraft === q) return;
    const timer = setTimeout(() => {
      setSearchParams((current) => updateCatalogFilters(current, { q: searchDraft }), { replace: true });
    }, 300);
    return () => clearTimeout(timer);
  }, [searchDraft, q, setSearchParams]);

  const toggleType = (type: string) => {
    updateFilters({ type: (selectedTypes.includes(type)
      ? selectedTypes.filter((item) => item !== type) : [...selectedTypes, type]).join(',') });
  };

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <ObjectsHeader freshness={freshness} />
      <FilterToolbar>
        <FilterChipGroup
          options={TYPE_TOGGLES}
          selected={selectedTypes}
          onToggle={toggleType}
        />
        <FilterSep />
        <Input
          allowClear
          size="small"
          placeholder="Поиск…"
          style={{ width: 220 }}
          value={searchDraft}
          onChange={(event) => setSearchDraft(event.target.value)}
        />
        <Select
          size="small"
          style={{ width: 130 }}
          value={status}
          options={[
            { value: 'active', label: 'Активные' },
            { value: 'deleted', label: 'Удалённые' },
          ]}
          onChange={(value) => updateFilters({ status: value })}
        />
        <FilterClear
          visible={selectedTypes.length > 0 || Boolean(searchDraft) || Boolean(filters.database)
            || Boolean(filters.schema) || Boolean(filters.source) || Boolean(filters.changedSince)}
          onClick={() => {
            updateFilters({ type: undefined, q: undefined, database: undefined,
              schema: undefined, source: undefined, changedSince: undefined });
          }}
        />
      </FilterToolbar>
      <Space size={4} wrap>
        {([
          ['database', 'База данных'], ['schema', 'Схема'], ['source', 'Источник'],
          ['changedSince', 'Изменены с'],
        ] as const).map(([key, label]) => filters[key] ? (
          <Tag key={key} closable onClose={() => updateFilters({ [key]: undefined })}>
            {label}: {filters[key]}
          </Tag>
        ) : null)}
      </Space>
      <ObjectsGrid filters={filters} onFreshness={onFreshness} />
    </Space>
  );
};

export default ObjectsPage;
