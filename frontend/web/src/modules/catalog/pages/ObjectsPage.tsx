import { listAssets } from '@shared/api/generated';
import type { AssetListItem, AssetListResponse } from '@shared/api/generated';
import { Card, Input, Select, Space, Table, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import FreshnessBar from '../components/FreshnessBar';
import { formatBytes, formatDateTime, formatRows } from '../format';

const TYPE_OPTIONS = [
  { value: 'TABLE', label: 'TABLE' },
  { value: 'VIEW', label: 'VIEW' },
  { value: 'MATERIALIZED_VIEW', label: 'MATERIALIZED_VIEW' },
  { value: 'SCHEMA', label: 'SCHEMA' },
  { value: 'DATABASE', label: 'DATABASE' },
  { value: 'PROCESS', label: 'PROCESS' },
  { value: 'EXTRACTION_SOURCE', label: 'EXTRACTION_SOURCE' },
  { value: 'STORAGE_LOCATION', label: 'STORAGE_LOCATION' },
];

const ObjectsPage = () => {
  const navigate = useNavigate();
  const [q, setQ] = useState('');
  const [type, setType] = useState<string | undefined>('TABLE');
  const [status, setStatus] = useState<'active' | 'deleted'>('active');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AssetListResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listAssets({ q: q || undefined, type, status, page, pageSize: 25 })
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
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
  }, [q, type, status, page]);

  const columns: ColumnsType<AssetListItem> = useMemo(
    () => [
      { title: 'Object', dataIndex: 'display_name', render: (value, row) => value || row.qualified_name },
      { title: 'Type', dataIndex: 'asset_type', width: 160 },
      { title: 'Size', dataIndex: ['metrics', 'total_bytes'], render: (value) => formatBytes(value), width: 120 },
      { title: 'Rows', dataIndex: ['metrics', 'row_estimate'], render: (value) => formatRows(value), width: 120 },
      { title: 'Changed', dataIndex: 'last_changed_at', render: (value) => formatDateTime(value), width: 180 },
    ],
    []
  );

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div>
        <Typography.Title level={2} style={{ marginBottom: 4 }}>
          Objects
        </Typography.Title>
        <FreshnessBar items={data?.collector_freshness} />
      </div>
      <Card>
        <Space wrap>
          <Input.Search
            allowClear
            placeholder="Search objects"
            style={{ width: 360 }}
            onSearch={(value) => {
              setPage(1);
              setQ(value);
            }}
          />
          <Select
            allowClear
            placeholder="Type"
            style={{ width: 220 }}
            options={TYPE_OPTIONS}
            value={type}
            onChange={(value) => {
              setPage(1);
              setType(value);
            }}
          />
          <Select
            style={{ width: 160 }}
            value={status}
            options={[
              { value: 'active', label: 'Active' },
              { value: 'deleted', label: 'Deleted' },
            ]}
            onChange={(value) => {
              setPage(1);
              setStatus(value);
            }}
          />
        </Space>
      </Card>
      <Table
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={data?.items || []}
        pagination={{
          current: page,
          pageSize: data?.page_size || 25,
          total: data?.total || 0,
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
