import { BookOutlined } from '@ant-design/icons';
import { Alert, Button, Divider, Drawer, Empty, Space, Typography } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { MarkdownContent } from './MarkdownContent';
import type { ApplicationHelpConfig, HelpTopic } from './types';

const normalizePath = (pathname: string) => pathname.replace(/\/$/, '') || '/';

export const resolveHelpTopic = (topics: HelpTopic[], pathname: string): HelpTopic | null => {
  const normalizedPathname = normalizePath(pathname);
  return topics.find(
    (topic) => topic.route && (
      normalizedPathname === topic.route
      || normalizedPathname.startsWith(`${topic.route}/`)
    ),
  ) ?? null;
};

export const resolveHelpTopicById = (topics: HelpTopic[], id: string): HelpTopic | null =>
  topics.find((topic) => topic.id === id) ?? null;

export type ApplicationHelpDrawerProps = ApplicationHelpConfig;

export function ApplicationHelpDrawer({
  topics,
  buttonLabel = 'Справка',
  buttonAriaLabel = 'Открыть справку по текущему экрану',
  drawerTitle = 'Справка',
  emptyDescription = 'Справка пока не добавлена',
  contextualMessage = 'Контекстная справка',
  routeDescriptionPrefix = 'Документ привязан к текущему экрану:',
  generalDescription = 'Общий документ справки',
  drawerWidth = 720,
  tableOfContentsTitle = 'Все разделы руководства',
  assetUrls,
}: ApplicationHelpDrawerProps) {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const routeTopic = useMemo(() => resolveHelpTopic(topics, location.pathname), [location.pathname, topics]);
  const topic = selectedTopicId ? resolveHelpTopicById(topics, selectedTopicId) : routeTopic;

  useEffect(() => {
    setSelectedTopicId(null);
  }, [location.pathname]);

  const tableOfContents = topics.length > 0 && (
    <>
      {topic ? <Divider style={{ marginTop: 32 }} /> : null}
      <Typography.Title level={5} style={{ marginTop: topic ? 0 : 8 }}>
        {tableOfContentsTitle}
      </Typography.Title>
      <Space direction="vertical" size={4} style={{ display: 'flex' }}>
        {topics.map((item) => (
          item.id === topic?.id
            ? <Typography.Text key={item.id} strong>{item.title}</Typography.Text>
            : (
              <Typography.Link key={item.id} onClick={() => setSelectedTopicId(item.id)}>
                {item.title}
              </Typography.Link>
            )
        ))}
      </Space>
    </>
  );

  return (
    <>
      <Button
        icon={<BookOutlined />}
        onClick={() => setOpen(true)}
        type={topic ? 'default' : 'text'}
        aria-label={buttonAriaLabel}
      >
        {buttonLabel}
      </Button>
      <Drawer
        title={topic?.title ?? drawerTitle}
        open={open}
        onClose={() => setOpen(false)}
        placement="right"
        width={drawerWidth}
        styles={{ body: { paddingTop: 12 } }}
      >
        {topic ? (
          <>
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
              message={contextualMessage}
              description={topic.route
                ? <Typography.Text type="secondary">{routeDescriptionPrefix} {topic.route}</Typography.Text>
                : <Typography.Text type="secondary">{generalDescription}</Typography.Text>}
            />
            <MarkdownContent content={topic.content} onHelpLink={setSelectedTopicId} assetUrls={assetUrls} />
          </>
        ) : (
          topics.length === 0 ? <Empty description={emptyDescription} /> : null
        )}
        {tableOfContents}
      </Drawer>
    </>
  );
}
