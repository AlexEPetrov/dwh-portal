import { UploadOutlined } from '@ant-design/icons';
import { Button, Space, Typography } from 'antd';

const DocumentUploadPage = () => (
  <Space
    direction="vertical"
    align="center"
    size={16}
    style={{
      width: '100%',
      minHeight: '60vh',
      justifyContent: 'center',
    }}
  >
    <Typography.Title level={2} style={{ margin: 0 }}>
      Документы
    </Typography.Title>
    <Typography.Paragraph type="secondary" style={{ margin: 0 }}>
      Загрузка документов будет подключена позже.
    </Typography.Paragraph>
    <Button type="primary" size="large" icon={<UploadOutlined />}>
      Загрузить
    </Button>
  </Space>
);

export default DocumentUploadPage;
