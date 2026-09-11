import { useApplicationAuth } from '../runtime';
import { LoginPage, type LoginPageProps } from './LoginPage';

export type ApplicationLoginPageProps = Omit<LoginPageProps, 'onLogin' | 'loading'>;

export function ApplicationLoginPage(props: ApplicationLoginPageProps) {
  const { login, isLoading } = useApplicationAuth();
  return <LoginPage {...props} onLogin={login} loading={isLoading} />;
}
