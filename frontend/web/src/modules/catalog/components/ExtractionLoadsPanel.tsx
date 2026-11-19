import type { LoadFileItem } from '@shared/api/generated';
import { formatBytes, formatDateTime } from '@shared/ui/portal';
import { Alert, Card, Empty, Spin, Table } from 'antd';
import { useState } from 'react';
import { useCatalogLoads } from '../queries';

type Props = {
  assetId: string;
  hideWhenUnavailable?: boolean;
  compact?: boolean;
};

const PAGE_SIZE_OPTIONS = ['20', '50', '100'];

const ExtractionLoadsContent = ({ assetId, hideWhenUnavailable = false, compact = false }: Props) => {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const loadsQuery = useCatalogLoads(assetId, page, pageSize);
  const payload = loadsQuery.data;

  if (loadsQuery.isError) {
    return <Alert type="error" showIcon message="Не удалось загрузить журнал загрузок" description={loadsQuery.error.message} />;
  }
  if (!payload) {
    return <Spin tip="Загрузка журнала…"><div style={{ minHeight: 80 }} /></Spin>;
  }
  if (hideWhenUnavailable && !payload.available) {
    return null;
  }

  if (payload && !payload.available) {
    return <Empty description="Журнал загрузок недоступен для этого объекта" />;
  }

  const table = (
    <Table<LoadFileItem>
      rowKey="id"
      size="small"
      loading={loadsQuery.isFetching}
      dataSource={payload?.items ?? []}
      locale={{ emptyText: 'Нет загруженных файлов' }}
      scroll={compact ? { y: 280 } : undefined}
      pagination={{
        current: page,
        pageSize,
        total: payload?.total ?? 0,
        showSizeChanger: true,
        pageSizeOptions: PAGE_SIZE_OPTIONS,
        showTotal: (total) => `${total}`,
        onChange: (nextPage, nextSize) => {
          setPage(nextSize === pageSize ? nextPage : 1);
          setPageSize(nextSize);
        },
      }}
      columns={[
        { title: 'Файл', dataIndex: 'file_name', ellipsis: true },
        {
          title: 'Загружен',
          dataIndex: 'loaded_at',
          width: 180,
          render: (value: string | null | undefined) => formatDateTime(value),
        },
        {
          title: 'Размер',
          dataIndex: 'file_size',
          width: 110,
          render: (value: number | null | undefined) => formatBytes(value),
        },
        { title: 'Статус', dataIndex: 'status', width: 90, render: (value) => value ?? '—' },
        {
          title: 'Длительность, с',
          dataIndex: 'load_duration_sec',
          width: 140,
          render: (value: number | null | undefined) =>
            value === null || value === undefined ? '—' : value,
        },
      ]}
    />
  );

  if (!compact) {
    return table;
  }

  return (
    <Card title="Загрузки" size="small" style={{ flex: '0 0 auto' }}>
      {table}
    </Card>
  );
};

// Remount pagination with the asset so no request uses the previous asset's page.
const ExtractionLoadsPanel = (props: Props) => <ExtractionLoadsContent key={props.assetId} {...props} />;

export default ExtractionLoadsPanel;
