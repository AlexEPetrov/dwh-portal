import type { ReportingMonitoringSourceRowItem } from '@shared/api/generated/types.gen';
import type { TableColumnsType } from 'antd';
import { Input, Pagination, Select, Space, Spin, Table, Typography } from 'antd';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

type MonitoringSourceTableProps = {
  rows: ReportingMonitoringSourceRowItem[];
  loading?: boolean;
  search: string;
  onSearchChange: (value: string) => void;
  pageTitleFilter?: string;
  onPageTitleFilterChange: (value: string | undefined) => void;
  page: number;
  pageSize: number;
  onPageChange: (page: number, pageSize: number) => void;
  selectedValue?: string | null;
  selectedRowKey?: string | null;
  prioritizeSelected?: boolean;
  onSelectValue?: (value: string | null) => void;
  onSelectRow?: (row: ReportingMonitoringSourceRowItem | null, rowKey: string | null) => void;
  onActivateValue?: (value: string) => void;
  headerExtra?: ReactNode;
  emptyText?: string;
  searchPlaceholder?: string;
  scrollY?: string | number | 'auto';
};

type IndexedMonitoringSourceRowItem = ReportingMonitoringSourceRowItem & {
  __rowKey: string;
  __sourceIndex: number;
};

export const buildMonitoringPageTitleOptions = <TRow extends ReportingMonitoringSourceRowItem>(
  rows: TRow[],
): Array<{ label: string; value: string }> =>
  Array.from(new Set(rows.map((item) => item.page_title).filter(Boolean)))
    .sort((left, right) => left.localeCompare(right))
    .map((item) => ({ label: item, value: item }));

export const filterMonitoringSourceRows = <TRow extends ReportingMonitoringSourceRowItem>(
  rows: TRow[],
  pageTitleFilter: string | undefined,
  search: string,
): TRow[] => {
  const normalizedSearch = (search || '').trim().toLowerCase();

  return rows.filter((item) => {
    const rawValues = item.raw_values || {};

    if (pageTitleFilter && item.page_title !== pageTitleFilter) {
      return false;
    }

    if (!normalizedSearch) {
      return true;
    }

    const haystack = [
      item.page_title,
      item.subheader,
      item.entity_name,
      item.metric_name,
      item.metric_period,
      item.metric_value,
      item.label || '',
      item.value || '',
      ...Object.values(rawValues),
    ]
      .join(' ')
      .toLowerCase();

    return haystack.includes(normalizedSearch);
  });
};

const getMonitoringSourceRowKey = (
  row: ReportingMonitoringSourceRowItem,
  index: number,
): string =>
  [
    row.value || 'no-value',
    JSON.stringify(row.raw_values || {}),
    row.page_title,
    row.subheader,
    row.entity_name,
    row.metric_name,
    row.metric_period,
    row.metric_value,
    String(index),
  ].join('::');

const MonitoringSourceTable = ({
  rows,
  loading = false,
  search,
  onSearchChange,
  pageTitleFilter,
  onPageTitleFilterChange,
  page,
  pageSize,
  onPageChange,
  selectedValue,
  selectedRowKey,
  prioritizeSelected = false,
  onSelectValue,
  onSelectRow,
  onActivateValue,
  headerExtra,
  emptyText = 'Нет данных',
  searchPlaceholder = 'Поиск по page/subheader/entity/metric/value',
  scrollY = 'calc(100vh - 335px)',
}: MonitoringSourceTableProps) => {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const controlsRef = useRef<HTMLDivElement | null>(null);
  const paginationRef = useRef<HTMLDivElement | null>(null);
  const [autoScrollY, setAutoScrollY] = useState(240);

  useEffect(() => {
    if (scrollY !== 'auto') return;

    const updateAutoScrollY = () => {
      const rootHeight = rootRef.current?.clientHeight ?? 0;
      const controlsHeight = controlsRef.current?.offsetHeight ?? 0;
      const paginationHeight = paginationRef.current?.offsetHeight ?? 0;
      const gapHeight = 24;
      const tableHeaderHeight = 40;
      setAutoScrollY(Math.max(120, rootHeight - controlsHeight - paginationHeight - gapHeight - tableHeaderHeight));
    };

    updateAutoScrollY();
    const resizeObserver = new ResizeObserver(updateAutoScrollY);
    if (rootRef.current) resizeObserver.observe(rootRef.current);
    if (controlsRef.current) resizeObserver.observe(controlsRef.current);
    if (paginationRef.current) resizeObserver.observe(paginationRef.current);

    return () => resizeObserver.disconnect();
  }, [scrollY]);

  const tableScrollY = scrollY === 'auto' ? autoScrollY : scrollY;

  const indexedRows = useMemo<IndexedMonitoringSourceRowItem[]>(
    () => rows.map((item, sourceIndex) => ({ ...item, __sourceIndex: sourceIndex, __rowKey: getMonitoringSourceRowKey(item, sourceIndex) })),
    [rows],
  );

  const pageTitleOptions = useMemo(() => buildMonitoringPageTitleOptions(indexedRows), [indexedRows]);

  const filteredRows = useMemo(
    () => filterMonitoringSourceRows(indexedRows, pageTitleFilter, search),
    [indexedRows, pageTitleFilter, search],
  );

  const prioritizedRows = useMemo(() => {
    if (!prioritizeSelected || (!selectedValue && !selectedRowKey)) {
      return filteredRows;
    }

    return filteredRows
      .map((row, index) => ({
        row,
        index,
        priority:
          selectedRowKey && row.__rowKey === selectedRowKey ? 0 : selectedValue && row.value === selectedValue ? 1 : 2,
      }))
      .sort((left, right) => left.priority - right.priority || left.index - right.index)
      .map(({ row }) => row);
  }, [filteredRows, prioritizeSelected, selectedRowKey, selectedValue]);

  const paginatedRows = useMemo(() => {
    const startIndex = (page - 1) * pageSize;
    return prioritizedRows.slice(startIndex, startIndex + pageSize);
  }, [page, pageSize, prioritizedRows]);

  useEffect(() => {
    const totalPages = Math.max(1, Math.ceil(prioritizedRows.length / pageSize));
    if (page > totalPages) {
      onPageChange(totalPages, pageSize);
    }
  }, [onPageChange, page, pageSize, prioritizedRows.length]);

  const selectedRowKeys = useMemo(() => {
    if (!selectedRowKey) return [];
    const selectedRow = paginatedRows.find((item) => item.__rowKey === selectedRowKey);
    return selectedRow ? [selectedRow.__rowKey] : [];
  }, [paginatedRows, selectedRowKey]);

  const rawColumnKeys = useMemo(
    () => Array.from(new Set(indexedRows.flatMap((row) => Object.keys(row.raw_values || {})))).sort((left, right) => left.localeCompare(right)),
    [indexedRows],
  );

  const rawColumns = useMemo<TableColumnsType<IndexedMonitoringSourceRowItem>>(() => {
    return rawColumnKeys
      .sort((left, right) => left.localeCompare(right))
      .map((key) => ({
        title: key,
        key: `raw:${key}`,
        width: 160,
        render: (_: unknown, row) => row.raw_values?.[key] || <Typography.Text type="secondary">—</Typography.Text>,
      }));
  }, [rawColumnKeys]);

  const legacyColumns: TableColumnsType<IndexedMonitoringSourceRowItem> = [
    {
      title: 'Page title',
      dataIndex: 'page_title',
      key: 'page_title',
      width: '18%',
    },
    {
      title: 'Subheader',
      dataIndex: 'subheader',
      key: 'subheader',
      width: '16%',
      render: (value: string) => value || <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: 'Entity',
      dataIndex: 'entity_name',
      key: 'entity_name',
      width: '16%',
    },
    {
      title: 'Metric',
      dataIndex: 'metric_name',
      key: 'metric_name',
      width: '16%',
    },
    {
      title: 'Период',
      dataIndex: 'metric_period',
      key: 'metric_period',
      width: '12%',
      render: (value: string) => value || <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: 'Значение',
      dataIndex: 'metric_value',
      key: 'metric_value',
      width: '12%',
      render: (value: string) => value || <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: 'Позиция',
      dataIndex: 'value',
      key: 'value',
      width: '18%',
      render: (value?: string | null) =>
        value ? (
          <Typography.Text code style={{ fontSize: 12 }}>
            {decodeUriComponentSafe(value)}
          </Typography.Text>
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        ),
    },
  ];

  const columns: TableColumnsType<IndexedMonitoringSourceRowItem> = rawColumnKeys.length > 0 ? rawColumns : legacyColumns;

  const selectRow = (record: IndexedMonitoringSourceRowItem) => {
    if (!record.value || !onSelectValue) return;
    onSelectRow?.(record, record.__rowKey);
    onSelectValue(record.value);
  };

  return (
    <div ref={rootRef} style={{ width: '100%', height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Space ref={controlsRef} wrap style={{ width: '100%', justifyContent: 'space-between', alignItems: 'flex-start', flexShrink: 0 }}>
        <Space wrap>
          <Select
            style={{ width: 570 }}
            placeholder="Page title"
            value={pageTitleFilter}
            options={pageTitleOptions}
            onChange={(value) => onPageTitleFilterChange(value)}
            allowClear
            showSearch
            optionFilterProp="label"
          />
          <Input
            style={{ width: 320 }}
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder={searchPlaceholder}
          />
        </Space>
        <Space size={16}>
          {headerExtra}
          <Typography.Text type="secondary">Найдено: {filteredRows.length}</Typography.Text>
        </Space>
      </Space>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flex: 1, minHeight: 0, padding: 32 }}>
          <Spin />
        </div>
      ) : (
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
            <Table<IndexedMonitoringSourceRowItem>
              rowKey="__rowKey"
              size="small"
              pagination={false}
              scroll={{ y: tableScrollY }}
              dataSource={paginatedRows}
              columns={columns}
              locale={{ emptyText }}
              rowSelection={
                onSelectValue
                  ? {
                      type: 'radio',
                      selectedRowKeys,
                      onChange: (keys) => {
                        const nextKey = keys[0];
                        const nextRecord = paginatedRows.find((item) => item.__rowKey === nextKey);
                        if (nextRecord) {
                          selectRow(nextRecord);
                          return;
                        }
                        onSelectRow?.(null, null);
                        onSelectValue(null);
                      },
                      getCheckboxProps: (record) => ({
                        disabled: !record.value,
                      }),
                    }
                  : undefined
              }
              onRow={(record) => ({
                onClick: () => selectRow(record),
                onDoubleClick: () => {
                  if (record.value && onActivateValue) {
                    selectRow(record);
                    onActivateValue(record.value);
                  }
                },
              })}
            />
          </div>
          <div ref={paginationRef} style={{ display: 'flex', justifyContent: 'center', paddingTop: 12, flexShrink: 0 }}>
            <Pagination
              current={page}
              pageSize={pageSize}
              total={prioritizedRows.length}
              showSizeChanger
              pageSizeOptions={['10', '20', '50', '100']}
              onChange={(nextPage, nextPageSize) => onPageChange(nextPage, nextPageSize)}
            />
          </div>
        </div>
      )}
    </div>
  );
};

const decodeUriComponentSafe = (value: string): string => {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
};

export default MonitoringSourceTable;
