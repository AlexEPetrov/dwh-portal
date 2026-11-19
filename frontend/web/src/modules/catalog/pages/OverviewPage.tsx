import { FreshnessBar, changeGlyph, formatBytes } from '@shared/ui/portal';
import { Alert, Card, Col, Empty, List, Progress, Row, Space, Spin, Statistic, Tag, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useCatalogOverview } from '../queries';

const OverviewPage = () => {
  const navigate = useNavigate();
  const overviewQuery = useCatalogOverview();
  const data = overviewQuery.data;

  if (!data) {
    return overviewQuery.isError
      ? <Alert type="error" showIcon message="Не удалось загрузить overview" description={overviewQuery.error.message} />
      : <Spin tip="Загрузка overview…"><div style={{ minHeight: 160 }} /></Spin>;
  }

  const maxSchema = Math.max(1, ...(data?.storage_by_schema || []).map((row) => row.total_bytes));

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div>
        <Typography.Title level={2} style={{ marginBottom: 4 }}>
          DWH Overview
        </Typography.Title>
        <FreshnessBar items={data?.collector_freshness} />
      </div>
      {overviewQuery.isError ? <Alert type="error" showIcon message="Не удалось обновить overview" description={overviewQuery.error.message} /> : null}
      {overviewQuery.isFetching ? <Spin size="small" /> : null}
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="Objects" value={data?.asset_counts.total ?? '—'} />
            <Typography.Text type="secondary">
              {data?.asset_counts.tables ?? 0} tables · {data?.asset_counts.views ?? 0} views
            </Typography.Text>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="Total storage" value={formatBytes(data?.storage_totals.total_bytes)} />
            <Typography.Text type="secondary">
              {formatBytes(data?.storage_totals.table_bytes)} data · {formatBytes(data?.storage_totals.index_bytes)} indexes
            </Typography.Text>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="Changes 24h" value={data?.recent_changes.total ?? '—'} />
            <Space>
              <Tag color="green">+{data?.recent_changes.added ?? 0} added</Tag>
              <Tag>{data?.recent_changes.changed ?? 0} changed</Tag>
              <Tag color="red">{data?.recent_changes.removed ?? 0} removed</Tag>
            </Space>
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card title="Storage by schema">
            {data?.storage_by_schema.length ? (
              data.storage_by_schema.map((row) => (
                <div key={row.schema_name} style={{ marginBottom: 12 }}>
                  <Space align="start" style={{ width: '100%', justifyContent: 'space-between' }}>
                    <Space direction="vertical" size={0}>
                      <Typography.Text strong>{row.schema_name}</Typography.Text>
                      {row.description ? (
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          {row.description}
                        </Typography.Text>
                      ) : null}
                    </Space>
                    <Typography.Text>{formatBytes(row.total_bytes)}</Typography.Text>
                  </Space>
                  <Progress percent={Math.round((row.total_bytes / maxSchema) * 100)} showInfo={false} />
                </div>
              ))
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="Recent changes" extra={<Typography.Link onClick={() => navigate('/changes')}>Все</Typography.Link>}>
            <List
              dataSource={data?.recent_changes.items || []}
              locale={{ emptyText: 'Нет изменений' }}
              renderItem={(item) => (
                <List.Item onClick={() => navigate(`/objects/${item.asset_id}`)} style={{ cursor: 'pointer' }}>
                  <Space direction="vertical" size={0} style={{ width: '100%' }}>
                    <Space wrap>
                      <Tag>{changeGlyph(item.change_type)}</Tag>
                      <Typography.Text>{item.change_type}</Typography.Text>
                      {item.asset_type ? <Tag>{item.asset_type}</Tag> : null}
                      <Typography.Text strong>
                        {item.name || item.display_name || item.qualified_name || item.asset_id.slice(0, 8)}
                      </Typography.Text>
                    </Space>
                    {item.qualified_name ? (
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        {item.qualified_name}
                      </Typography.Text>
                    ) : null}
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </Space>
  );
};

export default OverviewPage;
