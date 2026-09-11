import { renderApplication } from '@asset-management/app-shell';
import ruRU from 'antd/locale/ru_RU';
import dayjs from 'dayjs';
import 'dayjs/locale/ru';
import { routerPromise } from './app/router';
import { authAdapter } from './app/adapters/authAdapter';
import { permissionAdapter } from './app/adapters/permissionAdapter';

dayjs.locale('ru');

async function enableMocking() {
  if (import.meta.env.DEV && import.meta.env.VITE_MOCK_ENABLED === 'true') {
    const { worker } = await import('./mocks/browser');
    return worker.start({ onUnhandledRequest: 'bypass' });
  }
}

enableMocking().then(async () => {
  const router = await routerPromise;
  renderApplication({
    root: document.getElementById('root')!,
    router,
    locale: ruRU,
    runtime: {
      auth: authAdapter,
      permissions: permissionAdapter,
    },
  });
});
