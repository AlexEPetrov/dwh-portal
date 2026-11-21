import { ExportOutlined } from '@ant-design/icons';
import type { ChangeSummaryItem } from '@shared/api/generated';
import {
  FilterChipGroup,
  FilterClear,
  FilterSep,
  FilterToolbar,
  FreshnessBar,
  formatDateTime,
} from '@shared/ui/portal';
import { Alert, Button, Card, Col, Row, Select, Space, Statistic, Table, Tag, Typography } from 'antd';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCatalogPeriodChanges } from '../queries';

const OP_TOGGLES = [
  { key: 'ADDED', label: 'Добавлено' },
  { key: 'CHANGED', label: 'Изменено' },
  { key: 'REMOVED', label: 'Удалено' },
] as const;

const TYPE_TOGGLES = [
  { key: 'TABLE', label: 'Table' },
  { key: 'VIEW', label: 'View' },
  { key: 'MATERIALIZED_VIEW', label: 'MV' },
  { key: 'DATA_SOURCE', label: 'Источник' },
  { key: 'EXTRACTION_SOURCE', label: 'Извлечение' },
  { key: 'PROCESS', label: 'Loader' },
  { key: 'STORAGE_LOCATION', label: 'Хранение' },
] as const;

const ALL_OPS = OP_TOGGLES.map((item) => item.key);
const ALL_TYPES = TYPE_TOGGLES.map((item) => item.key);

const changeBucket = (changeType: string): 'ADDED' | 'CHANGED' | 'REMOVED' | null => {
  if (changeType === 'ADDED') {
    return 'ADDED';
  }
  if (changeType === 'REMOVED') {
    return 'REMOVED';
  }
  if (
    changeType === 'RENAMED' ||
    changeType === 'STRUCTURE_CHANGED' ||
    changeType === 'DESCRIPTION_CHANGED'
  ) {
    return 'CHANGED';
  }
  return null;
};

const rowAssetType = (row: ChangeSummaryItem): string | null => {
  if (row.asset_type) {
    return row.asset_type;
  }
  return typeof row.details?.asset_type === 'string' ? row.details.asset_type : null;
};

const rowName = (row: ChangeSummaryItem): string => {
  const detailsName = typeof row.details?.name === 'string' ? row.details.name : null;
  const detailsQn =
    typeof row.details?.qualified_name === 'string' ? row.details.qualified_name : null;
  return row.name || row.display_name || detailsName || row.qualified_name || detailsQn || '—';
};

const ChangesPage = () => {
  const navigate = useNavigate();
  const [period, setPeriod] = useState<'1' | '7' | '30'>('7');
  const changesQuery = useCatalogPeriodChanges(Number(period));
  const data = changesQuery.data;
  /** Default: all pressed. */
  const [selectedOps, setSelectedOps] = useState<string[]>(() => [...ALL_OPS]);
  const [selectedTypes, setSelectedTypes] = useState<string[]>(() => [...ALL_TYPES]);

  const filtered = useMemo(() => {
    const items = data?.items || [];
    return items.filter((item) => {
      const bucket = changeBucket(item.change_type);
      if (!bucket || !selectedOps.includes(bucket)) {
        return false;
      }
      const assetType = rowAssetType(item);
      if (!assetType || !selectedTypes.includes(assetType)) {
        return false;
      }
      return true;
    });
  }, [data, selectedOps, selectedTypes]);

  const filteredStats = useMemo(() => {
    let added = 0;
    let changed = 0;
    let removed = 0;
    for (const item of filtered) {
      const bucket = changeBucket(item.change_type);
      if (bucket === 'ADDED') added += 1;
      else if (bucket === 'REMOVED') removed += 1;
      else if (bucket === 'CHANGED') changed += 1;
    }
    return { added, changed, removed };
  }, [filtered]);

  const toggleOp = (key: string) => {
    setSelectedOps((prev) =>
      prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key]
    );
  };

  const toggleType = (type: string) => {
    setSelectedTypes((prev) =>
      prev.includes(type) ? prev.filter((item) => item !== type) : [...prev, type]
    );
  };

  const clearFilters = () => {
    setSelectedOps([...ALL_OPS]);
    setSelectedTypes([...ALL_TYPES]);
  };

  const hasFilters =
    selectedOps.length !== ALL_OPS.length || selectedTypes.length !== ALL_TYPES.length;

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <div>
        <Typography.Title level={2} style={{ marginBottom: 4 }}>
          Изменения
        </Typography.Title>
        <FreshnessBar items={data?.collector_freshness} />
      </div>
      {changesQuery.isError ? <Alert type="error" showIcon message="Не удалось загрузить изменения" description={changesQuery.error.message} /> : null}

      <FilterToolbar>
        <Select
          size="small"
          value={period}
          style={{ width: 110 }}
          onChange={setPeriod}
          options={[
            { value: '1', label: '24 часа' },
            { value: '7', label: '7 дней' },
            { value: '30', label: '30 дней' },
          ]}
        />
        <FilterSep />
        <FilterChipGroup options={OP_TOGGLES} selected={selectedOps} onToggle={toggleOp} />
        <FilterSep />
        <FilterChipGroup options={TYPE_TOGGLES} selected={selectedTypes} onToggle={toggleType} />
        <FilterClear visible={hasFilters} onClick={clearFilters} />
      </FilterToolbar>

      <Row gutter={12}>
        <Col span={8}>
          <Card size="small">
            <Statistic title="Добавлено" value={data ? filteredStats.added : '—'} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="Изменено" value={data ? filteredStats.changed : '—'} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="Удалено" value={data ? filteredStats.removed : '—'} />
          </Card>
        </Col>
      </Row>
      <Table
        rowKey="id"
        loading={changesQuery.isPending || changesQuery.isFetching}
        locale={{ emptyText: changesQuery.isError ? 'Изменения недоступны' : changesQuery.isPending ? 'Загрузка…' : 'Нет изменений' }}
        dataSource={filtered}
        pagination={{ pageSize: 50, showSizeChanger: false }}
        onRow={(row) => ({
          onClick: () => navigate(`/objects/${row.asset_id}`),
          style: { cursor: 'pointer' },
        })}
        columns={[
          {
            title: 'Изменение',
            dataIndex: 'change_type',
            width: 180,
            render: (value) => value,
          },
          {
            title: 'Имя',
            key: 'name',
            render: (_, row) => {
              const detailsQn =
                typeof row.details?.qualified_name === 'string'
                  ? row.details.qualified_name
                  : null;
              const title = rowName(row);
              const assetType = rowAssetType(row);
              const qualified = row.qualified_name || detailsQn;
              return (
                <Space direction="vertical" size={0}>
                  <Space size={8} wrap>
                    {assetType ? <Tag>{assetType}</Tag> : null}
                    <Typography.Text strong>{title}</Typography.Text>
                  </Space>
                  {qualified && qualified !== title ? (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {qualified}
                    </Typography.Text>
                  ) : null}
                </Space>
              );
            },
          },
          {
            title: 'Обнаружено',
            dataIndex: 'detected_at',
            width: 180,
            render: (value) => formatDateTime(value),
          },
          {
            title: 'Подробности',
            dataIndex: 'details',
            ellipsis: true,
            render: (value) => (value?.summary as string) || JSON.stringify(value || {}),
          },
          {
            title: '',
            key: 'go',
            width: 48,
            align: 'center',
            render: (_, row) => (
              <Button
                type="text"
                size="small"
                title="Перейти"
                aria-label="Перейти"
                icon={<ExportOutlined />}
                onClick={(event) => {
                  event.stopPropagation();
                  navigate(`/objects/${row.asset_id}`);
                }}
              />
            ),
          },
        ]}
      />
    </Space>
  );
};

export default ChangesPage;
