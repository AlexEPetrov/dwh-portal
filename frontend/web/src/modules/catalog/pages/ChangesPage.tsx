import { listChanges } from '@shared/api/generated';
import type { ChangeListResponse } from '@shared/api/generated';
import { Card, Col, Row, Select, Space, Statistic, Table, Tag, Typography } from 'antd';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import FreshnessBar from '../components/FreshnessBar';
import { changeGlyph, formatDateTime } from '../format';

const ChangesPage = () => {
  const navigate = useNavigate();
  const [period, setPeriod] = useState<'1' | '7' | '30'>('7');
  const [data, setData] = useState<ChangeListResponse | null>(null);

  useEffect(() => {
    const since = new Date();
    since.setUTCDate(since.getUTCDate() - Number(period));
    let cancelled = false;
    listChanges({ since: since.toISOString(), pageSize: 100 }).then((payload) => {
      if (!cancelled) {
        setData(payload);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [period]);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <div>
          <Typography.Title level={2} style={{ marginBottom: 4 }}>
            Changes
          </Typography.Title>
          <FreshnessBar items={data?.collector_freshness} />
        </div>
        <Select
          value={period}
          onChange={setPeriod}
          options={[
            { value: '1', label: 'Last 24 hours' },
            { value: '7', label: 'Last 7 days' },
            { value: '30', label: 'Last 30 days' },
          ]}
        />
      </Space>
      <Row gutter={16}>
        <Col span={8}>
          <Card>
            <Statistic title="Added" value={data?.added ?? 0} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="Changed" value={data?.changed ?? 0} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="Removed" value={data?.removed ?? 0} />
          </Card>
        </Col>
      </Row>
      <Table
        rowKey="id"
        dataSource={data?.items || []}
        onRow={(row) => ({
          onClick: () => navigate(`/objects/${row.asset_id}`),
          style: { cursor: 'pointer' },
        })}
        columns={[
          {
            title: 'Change',
            dataIndex: 'change_type',
            render: (value) => (
              <Space>
                <Tag>{changeGlyph(value)}</Tag>
                {value}
              </Space>
            ),
          },
          { title: 'Detected', dataIndex: 'detected_at', render: (value) => formatDateTime(value) },
          {
            title: 'Details',
            dataIndex: 'details',
            render: (value) => (value?.summary as string) || JSON.stringify(value || {}),
          },
        ]}
      />
    </Space>
  );
};

export default ChangesPage;
