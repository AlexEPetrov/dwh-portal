import type { RecentLoadFileItem } from '@shared/api/generated';
import { formatBytes, formatDateTime } from '@shared/ui/portal';
import { Alert, Button, Card, Empty, Space, Table, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useCatalogRecentLoads } from '../queries';

const columns: ColumnsType<RecentLoadFileItem> = [
  { title: 'Файл', dataIndex: 'file_name', ellipsis: true,
    render: (value: string, row) => (
      <Space direction="vertical" size={0} style={{ maxWidth: '100%' }}>
        <Typography.Text ellipsis title={value}>{value || '—'}</Typography.Text>
        {row.extraction_source_id ? (
          <Typography.Text type="secondary" ellipsis title={row.extraction_source_id}>
            Источник: {row.extraction_source_id}
          </Typography.Text>
        ) : null}
      </Space>
    ) },
  { title: 'База данных', dataIndex: 'database', width: 150, ellipsis: true,
    render: (value: string | null) => value || '—' },
  { title: 'Загружен', dataIndex: 'loaded_at', width: 175, render: formatDateTime },
  { title: 'Размер', dataIndex: 'file_size', width: 100, render: formatBytes },
  { title: 'Статус', dataIndex: 'status', width: 80,
    render: (value: number | null) => value ?? '—' },
];

/** Own the live request so its loading/error state never replaces the snapshot overview. */
const RecentLoadsPanel = () => {
  const query = useCatalogRecentLoads();
  const data = query.data;
  return (
    <Card title="Последние загруженные файлы"
      extra={<Button type="link" size="small" loading={query.isFetching} onClick={() => { void query.refetch(); }}>Обновить</Button>}>
      <Typography.Paragraph type="secondary">Живой журнал загрузок; статус показан как в журнале.</Typography.Paragraph>
      {query.isError ? (
        <Alert type="error" showIcon message="Не удалось загрузить журнал файлов"
          description={query.error.message} />
      ) : data && !data.available ? (
        <Alert type="info" showIcon message="Журнал загрузок недоступен"
          description="DWH не настроена либо журнал или поле времени загрузки отсутствуют." />
      ) : (
        <Table<RecentLoadFileItem>
          size="small" columns={columns} dataSource={data?.items ?? []}
          rowKey={(row) => JSON.stringify([row.database, row.id, row.extraction_source_id, row.file_name, row.loaded_at])}
          pagination={false} loading={query.isPending || query.isFetching}
          scroll={{ x: 650 }}
          locale={{ emptyText: query.isPending ? 'Загрузка…' : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="В журнале пока нет файлов" /> }}
        />
      )}
      {data?.available && data.has_more && !query.isError ? (
        <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
          Последние {data.items.length} записей. История источника доступна на его вкладке «Загрузки».
        </Typography.Paragraph>
      ) : null}
    </Card>
  );
};

export default RecentLoadsPanel;
