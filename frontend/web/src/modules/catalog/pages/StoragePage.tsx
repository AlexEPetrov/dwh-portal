import { getStorage, getStorageHistory } from '@shared/api/generated';
import type { StorageHistoryResponse, StorageResponse } from '@shared/api/generated';
import { Card, Col, Empty, Progress, Row, Space, Statistic, Table, Typography } from 'antd';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FreshnessBar, formatBytes, formatDateTime, formatRows } from '@shared/ui/portal';

const StoragePage = () => {
  const navigate = useNavigate();
  const [storage, setStorage] = useState<StorageResponse | null>(null);
  const [history, setHistory] = useState<StorageHistoryResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getStorage(), getStorageHistory()]).then(([current, hist]) => {
      if (cancelled) {
        return;
      }
      setStorage(current);
      setHistory(hist);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const maxSchema = Math.max(1, ...(storage?.by_schema || []).map((row) => row.total_bytes));

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div>
        <Typography.Title level={2} style={{ marginBottom: 4 }}>
          Storage
        </Typography.Title>
        <Typography.Text type="secondary">As of {formatDateTime(storage?.as_of)}</Typography.Text>
        <div style={{ marginTop: 8 }}>
          <FreshnessBar items={storage?.collector_freshness} />
        </div>
      </div>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="Total" value={formatBytes(storage?.total_bytes)} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="Data" value={formatBytes(storage?.table_bytes)} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="Indexes" value={formatBytes(storage?.index_bytes)} />
          </Card>
        </Col>
      </Row>
      <Card title="By schema">
        {storage?.by_schema.length ? (
          storage.by_schema.map((row) => (
            <div key={row.schema_name} style={{ marginBottom: 12 }}>
              <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                <Typography.Text strong>{row.schema_name}</Typography.Text>
                <Typography.Text>{formatBytes(row.total_bytes)}</Typography.Text>
              </Space>
              <Progress percent={Math.round((row.total_bytes / maxSchema) * 100)} showInfo={false} />
            </div>
          ))
        ) : (
          <Empty />
        )}
      </Card>
      <Card title="Largest objects">
        <Table
          rowKey="asset_id"
          size="small"
          pagination={false}
          dataSource={storage?.largest_objects || []}
          onRow={(row) => ({ onClick: () => navigate(`/objects/${row.asset_id}`), style: { cursor: 'pointer' } })}
          columns={[
            { title: 'Object', dataIndex: 'display_name' },
            { title: 'Type', dataIndex: 'asset_type', width: 140 },
            { title: 'Size', dataIndex: 'total_bytes', render: (value) => formatBytes(value), width: 140 },
            { title: 'Rows', dataIndex: 'row_estimate', render: (value) => formatRows(value), width: 120 },
          ]}
        />
      </Card>
      <Card title="History">
        <Table
          rowKey="snapshot_at"
          size="small"
          pagination={false}
          dataSource={history?.items || []}
          columns={[
            { title: 'Snapshot', dataIndex: 'snapshot_at', render: (value) => formatDateTime(value) },
            { title: 'Total', dataIndex: 'total_bytes', render: (value) => formatBytes(value) },
            { title: 'Data', dataIndex: 'table_bytes', render: (value) => formatBytes(value) },
            { title: 'Indexes', dataIndex: 'index_bytes', render: (value) => formatBytes(value) },
          ]}
        />
      </Card>
    </Space>
  );
};

export default StoragePage;
