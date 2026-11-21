import { DownloadOutlined, FileExcelOutlined, MoreOutlined } from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { Button, Dropdown, Empty, Modal, Typography, message } from 'antd';
import { useState } from 'react';

interface DuckDbSqlTraceButtonProps {
  sql?: string[] | null;
  onDownloadData?: () => void;
  downloadLoading?: boolean;
  onExportExcel?: () => void;
  exportExcelLoading?: boolean;
}

const DuckDbSqlTraceButton: React.FC<DuckDbSqlTraceButtonProps> = ({
  sql,
  onDownloadData,
  downloadLoading = false,
  onExportExcel,
  exportExcelLoading = false,
}) => {
  const [open, setOpen] = useState(false);
  const [modalSize, setModalSize] = useState({ width: Math.round(window.innerWidth * 0.8), height: 560 });
  const queries = sql?.filter((query) => query.trim().length > 0) ?? [];

  const handleResizeStart = (event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    const startX = event.clientX;
    const startY = event.clientY;
    const startSize = modalSize;

    const handleMouseMove = (moveEvent: MouseEvent) => {
      setModalSize({
        width: Math.max(520, startSize.width + moveEvent.clientX - startX),
        height: Math.max(360, startSize.height + moveEvent.clientY - startY),
      });
    };

    const handleMouseUp = () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  const menuItems: MenuProps['items'] = [
    {
      key: 'duckdb-sql',
      label: 'Показать DuckDB SQL',
      icon: <MoreOutlined />,
    },
    {
      key: 'download-data',
      label: 'Скачать данные',
      icon: <DownloadOutlined />,
      disabled: !onDownloadData,
    },
    {
      key: 'export-excel',
      label: 'Экспорт в Excel',
      icon: <FileExcelOutlined />,
      disabled: !onExportExcel,
    },
  ];

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (key === 'duckdb-sql') {
      setOpen(true);
      return;
    }

    if (key === 'download-data') {
      if (onDownloadData) {
        onDownloadData();
        return;
      }
      message.info('Скачивание данных пока не реализовано');
      return;
    }

    if (key === 'export-excel' && onExportExcel) {
      onExportExcel();
    }
  };

  return (
    <>
      <Dropdown menu={{ items: menuItems, onClick: handleMenuClick }} trigger={['click']}>
        <Button icon={<MoreOutlined />} loading={downloadLoading || exportExcelLoading} />
      </Dropdown>
      <Modal
        title="DuckDB SQL"
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
        width={modalSize.width}
        styles={{ body: { height: modalSize.height, overflow: 'hidden', paddingBottom: 24 } }}
      >
        <div style={{ position: 'relative', height: '100%' }}>
          <div style={{ height: '100%', overflow: 'auto', paddingRight: 8 }}>
            {queries.length === 0 ? (
              <Empty description="SQL появится после применения фильтров" />
            ) : (
              queries.map((query, index) => (
                <div key={`${index}-${query.length}`} style={{ marginBottom: 16 }}>
                  {queries.length > 1 && <Typography.Text strong>Query {index + 1}</Typography.Text>}
                  <pre style={{ whiteSpace: 'pre-wrap', background: '#f5f5f5', padding: 12 }}>
                    {query}
                  </pre>
                </div>
              ))
            )}
          </div>
          <div
            onMouseDown={handleResizeStart}
            title="Изменить размер"
            style={{
              position: 'absolute',
              right: -8,
              bottom: -16,
              width: 18,
              height: 18,
              cursor: 'nwse-resize',
              borderRight: '2px solid #8c8c8c',
              borderBottom: '2px solid #8c8c8c',
            }}
          />
        </div>
      </Modal>
    </>
  );
};

export default DuckDbSqlTraceButton;
