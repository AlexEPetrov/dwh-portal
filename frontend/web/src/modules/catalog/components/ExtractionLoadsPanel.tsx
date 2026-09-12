import { listAssetLoads } from '@shared/api/generated';
import type { LoadFileItem, LoadFileListResponse } from '@shared/api/generated';
import { Card, Empty, Table } from 'antd';
import { useEffect, useState } from 'react';
import { formatBytes, formatDateTime } from '../format';

type Props = {
  assetId: string;
  hideWhenUnavailable?: boolean;
  compact?: boolean;
};

const PAGE_SIZE_OPTIONS = ['20', '50', '100'];

const ExtractionLoadsPanel = ({ assetId, hideWhenUnavailable = false, compact = false }: Props) => {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [payload, setPayload] = useState<LoadFileListResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setPage(1);
  }, [assetId]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listAssetLoads({ assetId, page, pageSize })
      .then((data) => {
        if (!cancelled) {
          setPayload(data);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [assetId, page, pageSize]);

  if (hideWhenUnavailable && (!payload || !payload.available)) {
    return null;
  }

  if (payload && !payload.available) {
    return <Empty description="Журнал загрузок недоступен для этого объекта" />;
  }

  const table = (
    <Table<LoadFileItem>
      rowKey="id"
      size="small"
      loading={loading}
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
          setPage(nextPage);
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

export default ExtractionLoadsPanel;
