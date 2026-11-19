import { FreshnessBar, formatBytes, formatDateTime, formatRows } from '@shared/ui/portal';
import { Alert, Card, Col, Empty, Progress, Row, Space, Spin, Statistic, Table, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useCatalogStorage, useCatalogStorageHistory } from '../queries';

const StoragePage = () => {
  const navigate = useNavigate();
  const storageQuery = useCatalogStorage();
  const historyQuery = useCatalogStorageHistory();
  const storage = storageQuery.data;
  const history = historyQuery.data;

  if (!storage) {
    return storageQuery.isError
      ? <Alert type="error" showIcon message="Не удалось загрузить storage" description={storageQuery.error.message} />
      : <Spin tip="Загрузка storage…"><div style={{ minHeight: 160 }} /></Spin>;
  }

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
      {storageQuery.isError ? <Alert type="error" showIcon message="Не удалось обновить storage" description={storageQuery.error.message} /> : null}
      {storageQuery.isFetching ? <Spin size="small" /> : null}
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
        {historyQuery.isError ? <Alert type="error" showIcon message="Не удалось загрузить историю хранения" description={historyQuery.error.message} /> : null}
        {history ? <FreshnessBar items={history.collector_freshness} /> : null}
        <Table
          rowKey="snapshot_at"
          loading={historyQuery.isPending || historyQuery.isFetching}
          locale={{ emptyText: historyQuery.isError ? 'История недоступна' : historyQuery.isPending ? 'Загрузка…' : 'Нет снимков' }}
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
