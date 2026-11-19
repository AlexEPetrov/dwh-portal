import {
  FreshnessBar,
  changeGlyph,
  formatBytes,
  formatDateTime,
  formatRows,
} from '@shared/ui/portal';
import { Alert, Button, Card, Descriptions, Empty, Space, Spin, Table, Tabs, Tag, Typography } from 'antd';
import { useNavigate, useParams } from 'react-router-dom';
import ExtractionLoadsPanel from '../components/ExtractionLoadsPanel';
import LineageGraph from '../components/LineageGraph';
import { useCatalogAsset, useCatalogChanges, useCatalogColumns, useCatalogLineage } from '../queries';

const nextStepHint = (assetType: string): string => {
  switch (assetType) {
    case 'DATA_SOURCE':
      return 'Дальше: откройте Lineage — увидите extraction sources и путь до таблиц.';
    case 'EXTRACTION_SOURCE':
      return 'Дальше: Lineage покажет storage и PROCESS; в Objects можно открыть связанный loader.';
    case 'PROCESS':
      return 'Дальше: Lineage — READS_FROM storage и WRITES_TO table (если get_metadata отработал).';
    case 'TABLE':
    case 'VIEW':
    case 'MATERIALIZED_VIEW':
      return 'Дальше: Lineage вверх по цепочке — откуда пришли данные.';
    default:
      return 'Дальше: карточка соседних объектов или Lineage, если есть data-flow рёбра.';
  }
};

const ObjectDetailPage = () => {
  const { assetId } = useParams<{ assetId: string }>();
  const navigate = useNavigate();
  const assetQuery = useCatalogAsset(assetId);
  const columnsQuery = useCatalogColumns(assetId);
  const lineageQuery = useCatalogLineage(assetId, Boolean(assetId));
  const changesQuery = useCatalogChanges({ assetId, pageSize: 20 }, Boolean(assetId));
  const asset = assetQuery.data;
  const lineage = lineageQuery.data;

  if (!assetId) return <Empty description="Объект не выбран" />;
  if (!asset) {
    if (assetQuery.isError) {
      const missing = 'status' in assetQuery.error && assetQuery.error.status === 404;
      return missing ? <Empty description="Объект не найден" />
        : <Alert type="error" showIcon message="Не удалось загрузить объект" description={assetQuery.error.message} />;
    }
    return <Spin tip="Загрузка объекта…"><div style={{ minHeight: 160 }} /></Spin>;
  }

  const showLoads =
    asset.asset_type === 'EXTRACTION_SOURCE' && asset.source_provider === 'extraction_registry';

  const tabItems = [
    {
      key: 'overview',
      label: 'Overview',
      children: (
        <Descriptions bordered column={2} size="small">
          <Descriptions.Item label="Описание" span={2}>
            {asset.description || '—'}
          </Descriptions.Item>
          <Descriptions.Item label="Database">{asset.database || '—'}</Descriptions.Item>
          <Descriptions.Item label="Schema">{asset.schema_name || '—'}</Descriptions.Item>
          <Descriptions.Item label="Size">{formatBytes(asset.metrics.total_bytes)}</Descriptions.Item>
          <Descriptions.Item label="Indexes">{formatBytes(asset.metrics.index_bytes)}</Descriptions.Item>
          <Descriptions.Item label="Rows">{formatRows(asset.metrics.row_estimate)}</Descriptions.Item>
          <Descriptions.Item label="Last scan">{formatDateTime(asset.last_seen_at)}</Descriptions.Item>
          <Descriptions.Item label="Source">{asset.source_provider}</Descriptions.Item>
          <Descriptions.Item label="Qualified name">{asset.qualified_name}</Descriptions.Item>
          <Descriptions.Item label="Source files" span={2}>
            {asset.source_files && asset.source_files.length > 0
              ? asset.source_files.join(', ')
              : '—'}
          </Descriptions.Item>
        </Descriptions>
      ),
    },
    {
      key: 'columns',
      label: 'Columns',
      children: (
        <Space direction="vertical" style={{ width: '100%' }}>
        {columnsQuery.isError ? <Alert type="error" showIcon message="Не удалось загрузить колонки" description={columnsQuery.error.message} /> : null}
        <Table
          rowKey="name"
          loading={columnsQuery.isPending || columnsQuery.isFetching}
          locale={{ emptyText: columnsQuery.isError ? 'Колонки недоступны' : columnsQuery.isPending ? 'Загрузка…' : 'Нет колонок' }}
          size="small"
          pagination={false}
          dataSource={columnsQuery.data?.items ?? []}
          columns={[
            { title: '#', dataIndex: 'ordinal', width: 60 },
            { title: 'Name', dataIndex: 'name' },
            { title: 'Type', dataIndex: 'data_type', width: 180 },
            {
              title: 'Nullable',
              dataIndex: 'nullable',
              width: 100,
              render: (value: boolean | null | undefined) => (value == null ? '—' : value ? 'yes' : 'no'),
            },
            {
              title: 'Описание',
              dataIndex: 'description',
              ellipsis: true,
              render: (value) => value || '—',
            },
          ]}
        />
        </Space>
      ),
    },
    {
      key: 'lineage',
      label: 'Lineage',
      children: lineageQuery.isError ? (
        <Alert type="error" showIcon message="Lineage недоступен" description={lineageQuery.error.message} />
      ) : lineage ? (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          {lineageQuery.isFetching ? <Spin size="small" /> : null}
          <FreshnessBar items={lineage.collector_freshness} />
          {lineage.unresolved_targets.length ? <Alert type="warning" showIcon message="Нерешённые цели" description={lineage.unresolved_targets.map((item) => item.qualified_name).join(', ')} /> : null}
          <Button type="link" style={{ padding: 0 }} onClick={() => navigate(`/lineage/${asset.id}`)}>
            Открыть на странице Lineage
          </Button>
          <LineageGraph
            key={asset.id}
            nodes={lineage.nodes}
            edges={lineage.edges}
            selectedAssetId={asset.id}
            fillHeight={false}
          />
        </Space>
      ) : (
        <Spin tip="Загрузка lineage…"><div style={{ minHeight: 120 }} /></Spin>
      ),
    },
    ...(showLoads
      ? [
          {
            key: 'loads',
            label: 'Загрузки',
            children: <ExtractionLoadsPanel key={asset.id} assetId={asset.id} />,
          },
        ]
      : []),
    {
      key: 'storage',
      label: 'Storage',
      children: (
        <Card>
          <Typography.Text>
            Data {formatBytes(asset.metrics.table_bytes)} · Indexes {formatBytes(asset.metrics.index_bytes)} ·
            Snapshot {formatDateTime(asset.metrics.snapshot_at)}
          </Typography.Text>
        </Card>
      ),
    },
    {
      key: 'changes',
      label: 'Changes',
      children: (
        <Space direction="vertical" style={{ width: '100%' }}>
        {changesQuery.isError ? <Alert type="error" showIcon message="Не удалось загрузить изменения" description={changesQuery.error.message} /> : null}
        {changesQuery.data ? <FreshnessBar items={changesQuery.data.collector_freshness} /> : null}
        <Table
          rowKey="id"
          loading={changesQuery.isPending || changesQuery.isFetching}
          locale={{ emptyText: changesQuery.isError ? 'Изменения недоступны' : changesQuery.isPending ? 'Загрузка…' : 'Нет изменений' }}
          size="small"
          pagination={false}
          dataSource={changesQuery.data?.items ?? []}
          onRow={(row) => ({
            onClick: () => navigate(`/objects/${row.asset_id}`),
            style: { cursor: 'pointer' },
          })}
          columns={[
            {
              title: 'Type',
              dataIndex: 'change_type',
              render: (value) => (
                <Space>
                  <Tag>{changeGlyph(value)}</Tag>
                  {value}
                </Space>
              ),
            },
            { title: 'Detected', dataIndex: 'detected_at', render: (value) => formatDateTime(value) },
          ]}
        />
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div>
        <Space align="center" wrap>
          <Typography.Title level={2} style={{ margin: 0 }}>
            {asset.display_name}
          </Typography.Title>
          <Tag>{asset.asset_type}</Tag>
          <Tag color={asset.status === 'deleted' ? 'red' : 'green'}>{asset.status}</Tag>
          <Button type="primary" onClick={() => navigate(`/lineage/${asset.id}`)}>
            Открыть Lineage
          </Button>
          <Button onClick={() => navigate('/objects')}>К списку</Button>
        </Space>
        <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 4 }}>
          {asset.description || 'Описание отсутствует'}
        </Typography.Paragraph>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
          {nextStepHint(asset.asset_type)}
        </Typography.Paragraph>
        <FreshnessBar items={asset.collector_freshness} />
      </div>
      {assetQuery.isError ? <Alert type="error" showIcon message="Не удалось обновить объект" description={assetQuery.error.message} /> : null}
      {assetQuery.isFetching ? <Spin size="small" /> : null}
      <Tabs key={asset.id} items={tabItems} />
    </Space>
  );
};

export default ObjectDetailPage;
