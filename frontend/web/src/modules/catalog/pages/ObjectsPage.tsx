import { listAssets } from '@shared/api/generated';
import type { AssetListItem, AssetListResponse } from '@shared/api/generated';
import { Button, Input, Select, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FilterChipGroup,
  FilterClear,
  FilterSep,
  FilterToolbar,
} from '../components/FilterToolbar';
import FreshnessBar from '../components/FreshnessBar';
import { formatBytes, formatDateTime, formatRows } from '../format';

const TYPE_TOGGLES = [
  { key: 'DATA_SOURCE', label: 'Source' },
  { key: 'EXTRACTION_SOURCE', label: 'Extract' },
  { key: 'PROCESS', label: 'Loader' },
  { key: 'TABLE', label: 'Table' },
  { key: 'VIEW', label: 'View' },
] as const;

const PAGE_SIZE = 25;

const ObjectsPage = () => {
  const navigate = useNavigate();
  /** Empty = show all types. */
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState<'active' | 'deleted'>('active');
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<AssetListItem[]>([]);
  const [freshness, setFreshness] = useState<AssetListResponse['collector_freshness']>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listAssets({ status, page: 1, pageSize: 200 })
      .then((payload) => {
        if (!cancelled) {
          setItems(payload.items);
          setFreshness(payload.collector_freshness);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [status]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return items.filter((item) => {
      if (selectedTypes.length > 0 && !selectedTypes.includes(item.asset_type)) {
        return false;
      }
      if (!needle) {
        return true;
      }
      const haystack = [item.display_name, item.name, item.qualified_name, item.description]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(needle);
    });
  }, [items, selectedTypes, q]);

  const pageItems = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, page]);

  useEffect(() => {
    setPage(1);
  }, [selectedTypes, q, status]);

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
        loading={loading}
        columns={columns}
        dataSource={pageItems}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: filtered.length,
          onChange: setPage,
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
