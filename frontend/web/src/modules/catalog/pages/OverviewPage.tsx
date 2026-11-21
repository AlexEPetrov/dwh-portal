import { FreshnessBar, changeGlyph, formatBytes } from '@shared/ui/portal';
import { Alert, Card, Col, Empty, List, Progress, Row, Space, Spin, Statistic, Tag, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import OverviewSearch from '../components/OverviewSearch';
import { useCatalogOverview } from '../queries';

const OverviewPage = () => {
  const navigate = useNavigate();
  const overviewQuery = useCatalogOverview();
  const data = overviewQuery.data;

  const maxSchema = Math.max(1, ...(data?.storage_by_schema || []).map((row) => row.total_bytes));

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div>
        <Typography.Title level={2} style={{ marginBottom: 4 }}>
          Обзор DWH
        </Typography.Title>
        {data ? <FreshnessBar items={data.collector_freshness} /> : null}
      </div>
      <OverviewSearch />
      {!data ? (
        overviewQuery.isError
          ? <Alert type="error" showIcon message="Не удалось загрузить обзор" description={overviewQuery.error.message} />
          : <Spin tip="Загрузка обзора…"><div style={{ minHeight: 160 }} /></Spin>
      ) : (
      <>
      {overviewQuery.isError ? <Alert type="error" showIcon message="Не удалось обновить обзор" description={overviewQuery.error.message} /> : null}
      {overviewQuery.isFetching ? <Spin size="small" /> : null}
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="Объекты" value={data?.asset_counts.total ?? '—'} />
            <Typography.Text type="secondary">
              Таблицы: {data?.asset_counts.tables ?? 0} · Представления: {data?.asset_counts.views ?? 0}
            </Typography.Text>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="Общий объём" value={formatBytes(data?.storage_totals.total_bytes)} />
            <Typography.Text type="secondary">
              Данные: {formatBytes(data?.storage_totals.table_bytes)} · Индексы: {formatBytes(data?.storage_totals.index_bytes)}
            </Typography.Text>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="Изменения за 24 часа" value={data?.recent_changes.total ?? '—'} />
            <Space>
              <Tag color="green">Добавлено: +{data?.recent_changes.added ?? 0}</Tag>
              <Tag>Изменено: {data?.recent_changes.changed ?? 0}</Tag>
              <Tag color="red">Удалено: {data?.recent_changes.removed ?? 0}</Tag>
            </Space>
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card title="Объём по схемам">
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
          <Card title="Последние изменения" extra={<Typography.Link onClick={() => navigate('/changes')}>Все</Typography.Link>}>
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
      </>
      )}
    </Space>
  );
};

export default OverviewPage;
