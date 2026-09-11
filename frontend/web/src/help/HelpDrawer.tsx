import { BookOutlined } from '@ant-design/icons';
import { Alert, Button, Drawer, Empty, Typography } from 'antd';
import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import MarkdownContent from './MarkdownContent';
import { resolveHelpTopic, resolveHelpTopicById } from './registry';

const HelpDrawer = () => {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const routeTopic = resolveHelpTopic(location.pathname);
  const topic = selectedTopicId ? resolveHelpTopicById(selectedTopicId) : routeTopic;

  useEffect(() => {
    setSelectedTopicId(null);
  }, [location.pathname]);

  return (
    <>
      <Button
        icon={<BookOutlined />}
        onClick={() => setOpen(true)}
        type={topic ? 'default' : 'text'}
        aria-label="Открыть справку по текущему экрану"
      >
        Справка
      </Button>
      <Drawer
        title={topic?.title ?? 'Справка'}
        open={open}
        onClose={() => setOpen(false)}
        placement="right"
        width={720}
        styles={{ body: { paddingTop: 12 } }}
      >
        {topic ? (
          <>
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
              message="Контекстная справка"
              description={topic.route ? <Typography.Text type="secondary">Документ привязан к текущему экрану: {topic.route}</Typography.Text> : <Typography.Text type="secondary">Общий документ справки</Typography.Text>}
            />
            <MarkdownContent content={topic.content} onHelpLink={setSelectedTopicId} />
          </>
        ) : (
          <Empty description="Для текущего экрана справка пока не добавлена" />
        )}
      </Drawer>
    </>
  );
};

export default HelpDrawer;
