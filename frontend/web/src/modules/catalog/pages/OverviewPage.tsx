import { FreshnessBar, changeGlyph } from '@shared/ui/portal';
import { Alert, Card, Col, List, Row, Space, Spin, Statistic, Tag, Typography } from 'antd';
import { Link, useNavigate } from 'react-router-dom';
import { OVERVIEW_ASSET_TYPES, catalogTypeUrl } from '../assetTypes';
import OverviewSearch from '../components/OverviewSearch';
import RecentLoadsPanel from '../components/RecentLoadsPanel';
import { useCatalogOverview } from '../queries';

const OverviewPage = () => {
  const navigate = useNavigate();
  const overviewQuery = useCatalogOverview();
  const data = overviewQuery.data;

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div>
        <Typography.Title level={2} style={{ marginBottom: 4 }}>Обзор DWH</Typography.Title>
        {data ? <FreshnessBar items={data.collector_freshness} /> : null}
      </div>
      <OverviewSearch />
      {overviewQuery.isError ? (
        <Alert type="error" showIcon message="Не удалось загрузить обзор" description={overviewQuery.error.message} />
      ) : null}
      {!data && overviewQuery.isPending ? <Spin tip="Загрузка обзора…"><div style={{ minHeight: 160 }} /></Spin> : null}
      {data ? (
            <Card title={
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, paddingBlock: 12, whiteSpace: 'normal' }}>
                <Space wrap>
                  <span>Объекты по типам</span>
                  <Link to="/objects">Всего: {data.asset_counts.total}</Link>
                </Space>
                <Space wrap size={8} style={{ marginLeft: 'auto', fontWeight: 400, fontSize: 13 }}>
                  <Link to="/changes">Изменения за 24 часа: {data.recent_changes.total}</Link>
                  <Tag color="green">Добавлено: +{data.recent_changes.added}</Tag>
                  <Tag>Изменено: {data.recent_changes.changed}</Tag>
                  <Tag color="red">Удалено: {data.recent_changes.removed}</Tag>
                </Space>
              </div>
            }>
              <Row gutter={[12, 12]}>
                {OVERVIEW_ASSET_TYPES.map(({ key, label }) => (
                  <Col key={key} xs={24} sm={12} lg={6}>
                    <Link to={catalogTypeUrl(key)} style={{ display: 'block', height: '100%' }}
                      aria-label={`${label}: ${data.asset_counts.by_type?.[key] ?? 'нет данных'}. Открыть объекты этого типа`}>
                      <Card size="small" hoverable style={{ height: '100%' }}>
                        <Statistic title={label} value={data.asset_counts.by_type?.[key] ?? '—'}
                          valueStyle={{ fontSize: 24 }} />
                      </Card>
                    </Link>
                  </Col>
                ))}
              </Row>
            </Card>
      ) : null}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={15}><RecentLoadsPanel /></Col>
        <Col xs={24} lg={9}>
          <Card title="Последние изменения" extra={<Link to="/changes">Все</Link>}>
            <List
              loading={overviewQuery.isPending}
              dataSource={data?.recent_changes.items ?? []}
              locale={{ emptyText: overviewQuery.isError ? 'Список изменений недоступен' : 'Нет изменений' }}
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
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>{item.qualified_name}</Typography.Text>
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
