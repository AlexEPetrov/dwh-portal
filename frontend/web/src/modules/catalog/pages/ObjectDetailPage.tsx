import { getAsset, getAssetColumns, getAssetLineage, listChanges } from '@shared/api/generated';
import type {
  AssetDetailResponse,
  ChangeSummaryItem,
  ColumnItem,
  LineageResponse,
} from '@shared/api/generated';
import { Button, Card, Descriptions, Empty, Space, Table, Tabs, Tag, Typography } from 'antd';
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import ExtractionLoadsPanel from '../components/ExtractionLoadsPanel';
import FreshnessBar from '../components/FreshnessBar';
import LineageGraph from '../components/LineageGraph';
import { changeGlyph, formatBytes, formatDateTime, formatRows } from '../format';

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
  const [asset, setAsset] = useState<AssetDetailResponse | null>(null);
  const [columns, setColumns] = useState<ColumnItem[]>([]);
  const [lineage, setLineage] = useState<LineageResponse | null>(null);
  const [changes, setChanges] = useState<ChangeSummaryItem[]>([]);

  useEffect(() => {
    if (!assetId) {
      return undefined;
    }
    let cancelled = false;
    Promise.all([
      getAsset({ assetId }),
      getAssetColumns({ assetId }),
      getAssetLineage({ assetId }),
      listChanges({ assetId, pageSize: 20 }),
    ]).then(([detail, columnList, lineagePayload, changeList]) => {
      if (cancelled) {
        return;
      }
      setAsset(detail);
      setColumns(columnList.items);
      setLineage(lineagePayload);
      setChanges(changeList.items);
    });
    return () => {
      cancelled = true;
    };
  }, [assetId]);

  if (!asset) {
    return <Empty description="Объект не найден или ещё загружается" />;
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
        <Table
          rowKey="name"
          size="small"
          pagination={false}
          dataSource={columns}
          columns={[
            { title: '#', dataIndex: 'ordinal', width: 60 },
            { title: 'Name', dataIndex: 'name' },
            { title: 'Type', dataIndex: 'data_type', width: 180 },
            {
              title: 'Nullable',
              dataIndex: 'nullable',
              width: 100,
              render: (value) => (value ? 'yes' : 'no'),
            },
            {
              title: 'Описание',
              dataIndex: 'description',
              ellipsis: true,
              render: (value) => value || '—',
            },
          ]}
        />
      ),
    },
    {
      key: 'lineage',
      label: 'Lineage',
      children: lineage ? (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Button type="link" style={{ padding: 0 }} onClick={() => navigate(`/lineage/${asset.id}`)}>
            Открыть на странице Lineage
          </Button>
          <LineageGraph
            nodes={lineage.nodes}
            edges={lineage.edges}
            selectedAssetId={asset.id}
            fillHeight={false}
          />
        </Space>
      ) : (
        <Empty />
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
        <Table
          rowKey="id"
          size="small"
          pagination={false}
          dataSource={changes}
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
      <Tabs items={tabItems} />
    </Space>
  );
};

export default ObjectDetailPage;
