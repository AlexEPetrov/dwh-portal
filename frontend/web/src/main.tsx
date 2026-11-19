import { renderApplication } from '@asset-management/app-shell';
import ruRU from 'antd/locale/ru_RU';
import dayjs from 'dayjs';
import 'dayjs/locale/ru';
import { authAdapter } from './app/adapters/authAdapter';
import { permissionAdapter } from './app/adapters/permissionAdapter';
import { queryClient } from './app/core/queryClient';
import { routerPromise } from './app/router';

dayjs.locale('ru');

async function enableMocking() {
  if (import.meta.env.DEV && import.meta.env.VITE_MOCK_ENABLED === 'true') {
    const { worker } = await import('./mocks/browser');
    return worker.start({ onUnhandledRequest: 'bypass' });
  }
}

Promise.all([enableMocking(), routerPromise]).then(([, router]) => {
  renderApplication({
    root: document.getElementById('root')!,
    router,
    locale: ruRU,
    queryClient,
    runtime: {
      auth: authAdapter,
      permissions: permissionAdapter,
    },
  });
}).catch((error: unknown) => {
  // Required modules fail closed. Do not render a partially composed application.
  console.error('Application startup failed', error);
  const root = document.getElementById('root');
  if (!root) return;
  const message = document.createElement('p');
  message.setAttribute('role', 'alert');
  message.textContent = 'Не удалось запустить приложение. Обязательный модуль недоступен или конфигурация некорректна.';
  const reload = document.createElement('button');
  reload.type = 'button';
  reload.textContent = 'Перезагрузить';
  reload.onclick = () => window.location.reload();
  root.replaceChildren(message, reload);
});
