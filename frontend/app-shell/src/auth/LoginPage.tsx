import { Alert, Button, Card, Form, Input, Typography } from 'antd';
import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

const { Title } = Typography;

export interface LoginPageProps {
  onLogin: (username: string, password: string) => Promise<void>;
  loading?: boolean;
  title?: string;
  usernameLabel?: string;
  passwordLabel?: string;
  submitLabel?: string;
  invalidCredentialsMessage?: string;
}

export function LoginPage({
  onLogin,
  loading = false,
  title = 'Вход',
  usernameLabel = 'Username',
  passwordLabel = 'Password',
  submitLabel = 'Войти',
  invalidCredentialsMessage = 'Неверный логин или пароль',
}: LoginPageProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);

  const defaultLocation = { pathname: '/', search: '' };
  const fromLocation = (location.state as { from?: { pathname?: string; search?: string } } | null)?.from || defaultLocation;
  const from = fromLocation.pathname || '/';
  const fromSearch = fromLocation.search || '';

  const onFinish = async (values: { username: string; password: string }) => {
    setError(null);
    try {
      await onLogin(values.username, values.password);
      navigate({ pathname: from, search: fromSearch }, { replace: true });
    } catch {
      setError(invalidCredentialsMessage);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <Card style={{ width: 420 }}>
        <Title level={3} style={{ marginTop: 0 }}>{title}</Title>
        {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} />}
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item name="username" label={usernameLabel} rules={[{ required: true, message: `Введите ${usernameLabel.toLowerCase()}` }]}>
            <Input autoFocus />
          </Form.Item>
          <Form.Item name="password" label={passwordLabel} rules={[{ required: true, message: 'Введите пароль' }]}>
            <Input.Password />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block>
            {submitLabel}
          </Button>
        </Form>
      </Card>
    </div>
  );
}
