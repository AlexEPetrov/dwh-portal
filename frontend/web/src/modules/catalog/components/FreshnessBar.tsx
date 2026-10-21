import type { FreshnessItem } from '@shared/api/generated';
import { Space, Tag, Typography } from 'antd';
import { formatDateTime } from '../format';

const STATUS_COLOR: Record<string, string> = {
  SUCCESS: 'success',
  PARTIAL: 'warning',
  FAILED: 'error',
  STALE: 'warning',
};

type Props = {
  items?: FreshnessItem[] | null;
};

const FreshnessBar = ({ items }: Props) => {
  if (!items?.length) {
    return <Typography.Text type="secondary">Снимки ещё не публиковались</Typography.Text>;
  }
  return (
    <Space wrap size={[8, 8]}>
      {items.map((item) => (
        <Tag key={item.collector_name} color={STATUS_COLOR[item.status] || 'default'}>
          {item.collector_name}: {item.status} · {formatDateTime(item.finished_at)}
        </Tag>
      ))}
    </Space>
  );
};

export default FreshnessBar;
