import { SendOutlined } from '@ant-design/icons';
import { Button, Card, Empty, Input, Space, Typography } from 'antd';
import { useState } from 'react';

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
};

const AssistantPage = () => {
  const [draft, setDraft] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const send = () => {
    const text = draft.trim();
    if (!text) {
      return;
    }
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      text,
    };
    const assistantMessage: ChatMessage = {
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      text: 'AI-чат будет подключён позже. Сейчас это заглушка интерфейса.',
    };
    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setDraft('');
  };

  return (
    <Space direction="vertical" size={12} style={{ width: '100%', height: '100%' }}>
      <Typography.Title level={2} style={{ marginBottom: 0 }}>
        Ассистент
      </Typography.Title>
      <Card
        styles={{
          body: {
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
            minHeight: '60vh',
          },
        }}
      >
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {messages.length === 0 ? (
            <Empty description="Задайте вопрос по каталогу DWH" />
          ) : (
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              {messages.map((message) => (
                <Card
                  key={message.id}
                  size="small"
                  style={{
                    alignSelf: message.role === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '80%',
                    marginLeft: message.role === 'user' ? 'auto' : 0,
                    background: message.role === 'user' ? '#f0f5ff' : undefined,
                  }}
                >
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {message.role === 'user' ? 'Вы' : 'Ассистент'}
                  </Typography.Text>
                  <div>{message.text}</div>
                </Card>
              ))}
            </Space>
          )}
        </div>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={draft}
            placeholder="Напишите сообщение…"
            onChange={(event) => setDraft(event.target.value)}
            onPressEnter={send}
          />
          <Button type="primary" icon={<SendOutlined />} onClick={send}>
            Отправить
          </Button>
        </Space.Compact>
      </Card>
    </Space>
  );
};

export default AssistantPage;
