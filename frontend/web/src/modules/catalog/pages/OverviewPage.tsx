import { getOverview } from '@shared/api/generated';
import type { OverviewResponse } from '@shared/api/generated';
import { Card, Col, Empty, List, Progress, Row, Space, Statistic, Tag, Typography } from 'antd';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import FreshnessBar from '../components/FreshnessBar';
import { changeGlyph, formatBytes } from '../format';

const OverviewPage = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getOverview()
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message || 'Не удалось загрузить overview');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const maxSchema = Math.max(1, ...(data?.storage_by_schema || []).map((row) => row.total_bytes));

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div>
        <Typography.Title level={2} style={{ marginBottom: 4 }}>
          DWH Overview
        </Typography.Title>
        <FreshnessBar items={data?.collector_freshness} />
      </div>
      {error ? <Typography.Text type="danger">{error}</Typography.Text> : null}
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
                  <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                    <Typography.Text strong>{row.schema_name}</Typography.Text>
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
                  <Space>
                    <Tag>{changeGlyph(item.change_type)}</Tag>
                    <Typography.Text>{item.change_type}</Typography.Text>
                    <Typography.Text type="secondary">{item.asset_id.slice(0, 8)}</Typography.Text>
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
