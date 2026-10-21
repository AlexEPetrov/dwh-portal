import { listAssets } from '@shared/api/generated';
import type { AssetListItem } from '@shared/api/generated';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Input, Select, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useDeferredValue, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
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

const TYPE_TOGGLES = [
  { key: 'DATA_SOURCE', label: 'Source' },
  { key: 'EXTRACTION_SOURCE', label: 'Extract' },
  { key: 'PROCESS', label: 'Loader' },
  { key: 'STORAGE_LOCATION', label: 'Storage' },
  { key: 'TABLE', label: 'Table' },
  { key: 'VIEW', label: 'View' },
] as const;

const PAGE_SIZE_OPTIONS = ['10', '25', '50', '100'] as const;

const ObjectsPage = () => {
  const navigate = useNavigate();
  /** Empty = show all types. Client/UI state — stays in useState, not Query. */
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [q, setQ] = useState('');
  const deferredQ = useDeferredValue(q.trim());
  const [status, setStatus] = useState<'active' | 'deleted'>('active');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const typeFilter = selectedTypes.length > 0 ? selectedTypes.join(',') : undefined;

  const assetsQuery = useQuery({
    queryKey: ['catalog', 'assets', { status, q: deferredQ, typeFilter, page, pageSize }],
    queryFn: () =>
      listAssets({
        status,
        page,
        pageSize,
        q: deferredQ || undefined,
        type: typeFilter,
      }),
  });

  const items = assetsQuery.data?.items ?? [];
  const total = assetsQuery.data?.total ?? 0;
  const freshness = assetsQuery.data?.collector_freshness ?? [];

  useEffect(() => {
    setPage(1);
  }, [selectedTypes, deferredQ, status]);

  const toggleType = (type: string) => {
    setSelectedTypes((prev) =>
      prev.includes(type) ? prev.filter((item) => item !== type) : [...prev, type]
    );
  };

  const columns: ColumnsType<AssetListItem> = useMemo(
    () => [
      {
        title: 'Object',
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
        title: 'Type',
        dataIndex: 'asset_type',
        width: 170,
        render: (value) => <Tag>{value}</Tag>,
      },
      {
        title: 'Source file',
        dataIndex: 'source_files',
        ellipsis: true,
        render: (value: string[] | undefined) => (value && value.length > 0 ? value.join(', ') : '—'),
      },
      {
        title: 'Size',
        dataIndex: ['metrics', 'total_bytes'],
        render: (value) => formatBytes(value),
        width: 120,
      },
      {
        title: 'Rows',
        dataIndex: ['metrics', 'row_estimate'],
        render: (value) => formatRows(value),
        width: 120,
      },
      {
        title: 'Changed',
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
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <div>
        <Typography.Title level={2} style={{ marginBottom: 4 }}>
          Objects
        </Typography.Title>
        <FreshnessBar items={freshness} />
      </div>
      {assetsQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message="Не удалось загрузить список объектов"
          description={assetsQuery.error instanceof Error ? assetsQuery.error.message : undefined}
        />
      ) : null}
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
          value={q}
          onChange={(event) => setQ(event.target.value)}
        />
        <Select
          size="small"
          style={{ width: 110 }}
          value={status}
          options={[
            { value: 'active', label: 'Active' },
            { value: 'deleted', label: 'Deleted' },
          ]}
          onChange={(value) => setStatus(value)}
        />
        <FilterClear
          visible={selectedTypes.length > 0 || Boolean(q.trim())}
          onClick={() => {
            setSelectedTypes([]);
            setQ('');
          }}
        />
      </FilterToolbar>
      <Table
        rowKey="id"
        loading={assetsQuery.isPending || assetsQuery.isFetching}
        columns={columns}
        dataSource={items}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          pageSizeOptions: [...PAGE_SIZE_OPTIONS],
          onChange: (nextPage, nextSize) => {
            setPage(nextPage);
            setPageSize(nextSize);
          },
        }}
        onRow={(row) => ({
          onClick: () => navigate(`/objects/${row.id}`),
          style: { cursor: 'pointer' },
        })}
      />
    </Space>
  );
};

export default ObjectsPage;
