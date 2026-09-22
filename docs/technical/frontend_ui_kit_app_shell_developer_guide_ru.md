# Developer Guide: UI Kit и Application Shell

**Область:** `frontend/ui-kit`, `frontend/app-shell`, `frontend/web`  
**Для кого:** разработчики, которые добавляют business-модули, создают новые intranet-приложения, расширяют общий UI или интегрируют auth / permissions / help / AI capabilities.  
**Применимо к:** текущему workspace после выделения `ui-kit` / `app-shell` и исправления Vite `import.meta.glob`.  
**Текущий статус архитектуры:** `ui-kit` и `app-shell` используются как source-workspace packages; отдельная сборка и публикация этих пакетов пока не обязательны.

---

## 1. Базовая модель

Frontend разделён на три слоя:

```text
frontend/
├── ui-kit/       переиспользуемый presentation layer
├── app-shell/    переиспользуемая инфраструктура приложения
└── web/          конкретное business-приложение
```

Разрешённые зависимости:

```text
web -> app-shell -> ui-kit
web -------------> ui-kit
```

Запрещённые зависимости:

```text
ui-kit    -X-> app-shell
ui-kit    -X-> web
app-shell -X-> web
app-shell -X-> business modules из web
app-shell -X-> generated application API
```

При выборе места для нового кода используйте простое правило:

```text
ui-kit
    = как выглядят и ведут себя переиспользуемые UI-элементы

app-shell
    = как устроено стандартное intranet-приложение

web
    = что делает конкретное business-приложение
```

Второе правило не менее важно:

```text
mechanism                         -> app-shell
business policy / implementation  -> web
```

Примеры:

| Что | Владелец |
|---|---|
| Внешний вид Button/Card/Grid | `ui-kit` |
| Standard header/sidebar/layout | `app-shell` |
| Механика PluginRegistry | `app-shell` |
| Как именно проверяются permissions | adapter в `web` |
| Permission `calculation/run` | business plugin в `web` |
| Как показывается contextual help | `app-shell` |
| Текст help по valuation analysis | `web` |
| Zustand store | `web` |
| Generic plugin contributions | `app-shell` |
| Интерпретация contribution как Zustand slice | `web` |

Не переносите код в `app-shell` только потому, что его используют две business-страницы. `app-shell` — это application platform, а не общий склад кода.

---

## 2. Workspace и установка

Canonical frontend workspace:

```text
frontend/
├── package.json
├── package-lock.json
├── web/
├── ui-kit/
└── app-shell/
```

Установка зависимостей выполняется из `frontend/`:

```bash
cd frontend
npm ci
```

Development:

```bash
npm run dev
```

Production build:

```bash
npm run build
```

Генерация API:

```bash
npm run gen-api
```

Не поддерживайте отдельные canonical lock-файлы и отдельные `node_modules` внутри `web`, `ui-kit` или `app-shell`.

Используйте `npm install` только когда намеренно меняете зависимости и хотите обновить корневой `package-lock.json`.

---

## 3. Package imports

Считайте `ui-kit` и `app-shell` полноценными packages, даже если сейчас они экспортируют исходники напрямую.

Рекомендуемые imports:

```ts
import { DataGrid } from '@asset-management/ui-kit/data-grid';
import { appTheme } from '@asset-management/ui-kit/theme';

import { renderApplication } from '@asset-management/app-shell';
import { MainFormLayout } from '@asset-management/app-shell/layout';
import { RouteSuspense } from '@asset-management/app-shell/routing';
import type { ModuleRegistration } from '@asset-management/app-shell/plugin';
```

Не импортируйте физические пути:

```ts
// Неправильно
import { DataGrid } from '../../ui-kit/src/data-grid/DataGrid';
```

Если нужен один subsystem, предпочтительнее subpath export:

```ts
// Предпочтительно
import { appTheme } from '@asset-management/ui-kit/theme';

// Допустимо, но шире
import { appTheme } from '@asset-management/ui-kit';
```

Это позволит позднее перейти с exports из `src` на exports из `dist` без массового изменения consumer-кода.

---

# 4. UI Kit

## 4.1 Что должно находиться в UI Kit

`frontend/ui-kit` владеет generic presentation и низкоуровневым reusable UI behavior.

Текущие публичные области:

```text
@asset-management/ui-kit/theme
@asset-management/ui-kit/data-grid
@asset-management/ui-kit/json-schema
@asset-management/ui-kit/styles.css
```

Хорошие кандидаты для UI Kit:

- generic controls;
- reusable form presentation;
- DataGrid infrastructure;
- design tokens;
- generic grid/table status components;
- generic loading/empty/feedback presentation;
- schema-form templates, не знающие business domain.

Плохие кандидаты:

- routes;
- authentication;
- application sidebar;
- permissions;
- backend clients;
- valuation/scenario semantics;
- application-specific stores;
- domain selectors вроде contract / observation-date controls.

---

## 4.2 Theme

Canonical theme:

```ts
import { appTheme } from '@asset-management/ui-kit/theme';
```

Это Ant Design `ThemeConfig`, в котором находятся application colors, typography, radii и per-component tokens.

Обычному приложению не нужно подключать тему вручную: `renderApplication()` использует её как default через `ApplicationProviders`.

Переопределяйте тему только если новое приложение действительно должно выглядеть иначе:

```tsx
renderApplication({
  root,
  router,
  locale,
  theme: anotherTheme,
  runtime,
});
```

Предпочитайте Ant Design design tokens вместо ad-hoc `.ant-*` CSS overrides.

### Шрифты

Если foundation CSS использует внешний Google Fonts import для Inter, это runtime/deployment dependency.

Для intranet, offline или restricted-network environment лучше:

1. self-hosted `WOFF2` assets Inter; либо
2. system font stack.

Не смешивайте такую инфраструктурную миграцию с обычной business-задачей.

---

## 4.3 Foundation styles

Стандартное приложение, которое запускается через:

```ts
renderApplication(...)
```

не должно вручную импортировать foundation CSS.

Shell сам подключает:

```text
@asset-management/ui-kit/styles.css
app-shell/styles.css
```

Не добавляйте новый application-global CSS только для того, чтобы заработал стандартный shell.

Business/module CSS должен лежать рядом с модулем:

```text
web/src/modules/calculations/styles.css
web/src/modules/contracts/styles.css
```

---

## 4.4 DataGrid

Import:

```ts
import { DataGrid } from '@asset-management/ui-kit/data-grid';
```

Пример:

```tsx
import type { ColDef } from 'ag-grid-community';
import { DataGrid } from '@asset-management/ui-kit/data-grid';

interface Row {
  id: string;
  value: number;
}

const columns: ColDef<Row>[] = [
  { field: 'id', headerName: 'ID' },
  { field: 'value', headerName: 'Value' },
];

export function ExampleGrid({ rows }: { rows: Row[] }) {
  return (
    <DataGrid
      rowData={rows}
      columnDefs={columns}
      enableRowSelection
      enableRangeSelection
      enableStatusBar
      height="100%"
      onSelectionChanged={(selectedRows) => {
        console.log(selectedRows);
      }}
    />
  );
}
```

Текущий wrapper добавляет общий AG Grid behavior:

- sorting/filtering/resizing по умолчанию;
- optional row selection;
- Community-edition range selection;
- Ctrl/Cmd-style range workflows;
- статистику выбранного диапазона через `AutosumStatusBar`.

Не заставляйте любой AG Grid use case проходить через `DataGrid`. Если специализированная таблица требует большого количества AG Grid APIs и wrapper становится слишком широким или «протекающим», используйте `AgGridReact` напрямую внутри business-модуля. Выносите общую функциональность только после появления реального повторного use case.

---

## 4.5 JSON-schema layouts

Public API:

```ts
import {
  DefaultFieldTemplate,
  GroupedObjectFieldTemplate,
  normalizeOptionalSchema,
} from '@asset-management/ui-kit/json-schema';
```

Используйте это для RJSF forms, которые следуют общим schema metadata conventions.

Поддерживаемые presentation metadata включают:

```text
ui:group
ui:full_width
ui:col_span
ui:col_span_by_breakpoint
ui:property_priority
ui:grid_columns*
```

`normalizeOptionalSchema()` полезен, когда generated schema описывает optional field через `anyOf` с одним non-null type и `null`.

UI Kit может интерпретировать **presentation metadata**, но не business meaning. Например, он может понимать `ui:group`, но не должен знать, что такое `valuation_type`, `gl_account` или `market`.

---

# 5. App Shell

## 5.1 Ответственность App Shell

`frontend/app-shell` владеет standard application mechanics, которые не должны копироваться в App2/App3:

- React application bootstrap;
- Ant Design и Query providers;
- runtime adapter contracts;
- standard auth/login boundary;
- permission guard/render mechanics;
- standard user menu;
- standard main layout;
- collapsed/hover sidebar behavior;
- plugin-aware navigation;
- contextual help mechanics;
- `MainFormLayout`;
- standard lazy-route suspense;
- router composition;
- plugin contracts, registry и registration mechanics;
- generic plugin contribution slots;
- shell viewport/layout CSS.

Shell намеренно не знает конкретный state manager, backend client, business roles или permission model.

---

# 6. Application bootstrap

`web/src/main.tsx` остаётся composition root конкретного приложения, но сама mechanics делегируется shell.

Пример:

```tsx
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
```

`renderApplication()` владеет:

```text
React root
StrictMode
ApplicationProviders
ApplicationRuntimeProvider
RouterProvider
UI-kit styles
shell styles
```

Основные options:

```ts
interface RenderApplicationOptions {
  root: HTMLElement;
  router: Router;
  locale?: ...;
  theme?: ThemeConfig;
  queryClient?: QueryClient;
  strictMode?: boolean;
  runtime?: ApplicationRuntimeAdapters;
}
```

Не ставьте `strictMode: false` только ради того, чтобы скрыть development warnings.

---

# 7. Runtime adapters

Shell знает, что приложение **может** иметь authentication и permissions. Как именно они реализованы, shell узнаёт только через adapters.

Это один из центральных архитектурных принципов:

```text
web implementation
      ↓
    Adapter
      ↓
ApplicationRuntime
      ↓
   app-shell
```

---

## 7.1 AuthAdapter

Contract:

```ts
interface ApplicationAuthState {
  user?: AppShellUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  bootstrapSession?: () => Promise<void>;
}

interface AuthAdapter {
  useAuthState: () => ApplicationAuthState;
}
```

Current web adapter связывает Zustand с shell:

```ts
import type { AuthAdapter } from '@asset-management/app-shell/runtime';
import { useStore } from '@app/core';

export const authAdapter: AuthAdapter = {
  useAuthState() {
    const user = useStore((state) => state.user);
    const isAuthenticated = useStore((state) => state.isAuthenticated);
    const isLoading = useStore((state) => state.isLoading);
    const login = useStore((state) => state.login);
    const logout = useStore((state) => state.logout);
    const bootstrapSession = useStore((state) => state.bootstrapSession);

    return {
      user,
      isAuthenticated,
      isLoading,
      login,
      logout,
      bootstrapSession,
    };
  },
};
```

Shell не должен импортировать `useStore`, `RootState`, API endpoints, cookie logic или X-API-Key handling.

Если App2 использует Keycloak, React Context, Redux или другой auth SDK, меняется только adapter.

---

## 7.2 PermissionAdapter

Contract:

```ts
interface PermissionRequirement<
  TAction extends string = string,
  TContext = unknown,
> {
  resource: string;
  action: TAction;
  context?: TContext;
}

interface PermissionAdapter {
  useCanAccess: () => (
    permission: PermissionRequirement,
  ) => boolean;
}
```

`context` намеренно opaque для shell.

Current application adapter:

```ts
export const permissionAdapter: PermissionAdapter = {
  useCanAccess() {
    const permissions = useStore((state) => state.permissions);

    return useCallback(
      (permission) =>
        canPerform(
          permissions,
          permission.resource,
          permission.action as Action,
          permission.context as Partial<PermissionRule['constraints']> | undefined,
        ),
      [permissions],
    );
  },
};
```

Итого:

```text
resource/action/context declaration -> business plugin
permission interpretation            -> web adapter
permission enforcement mechanics     -> shell
```

---

# 8. Permission-aware UI

## 8.1 Защита route/page

Используйте:

```tsx
import { ApplicationPermissionGuard } from '@asset-management/app-shell/auth';

<ApplicationPermissionGuard
  permission={{ resource: 'calculation', action: 'run' }}
>
  <CalculationRunPage />
</ApplicationPermissionGuard>
```

Если permission отсутствует, shell показывает standard access-denied presentation.

Не вызывайте ATRM-specific `canPerform()` напрямую только ради standard route protection. Для этого нужен shell guard.

---

## 8.2 Conditional render

Используйте:

```tsx
import { ApplicationCan } from '@asset-management/app-shell/auth';

<ApplicationCan
  permission={{ resource: 'contract', action: 'create' }}
>
  <CreateContractButton />
</ApplicationCan>
```

С fallback:

```tsx
<ApplicationCan
  permission={{ resource: 'contract', action: 'delete' }}
  fallback={<DisabledDeleteButton />}
>
  <DeleteButton />
</ApplicationCan>
```

С application-specific context:

```tsx
<ApplicationCan
  permission={{
    resource: 'market-data',
    action: 'edit',
    context: { market: 'sales_fabr' },
  }}
>
  <EditButton />
</ApplicationCan>
```

Только `PermissionAdapter` должен интерпретировать `context`.

Важно: frontend permissions — это UX/access-visibility layer, а не security boundary. Backend API обязан независимо проверять authorization.

---

# 9. Application metadata и standard layout

Standard application должно описывать себя декларативно вместо собственных `MainLayout`, `SideMenu`, `UserMenu`.

Пример:

```tsx
import { HomeOutlined } from '@ant-design/icons';
import type { ApplicationLayoutProps } from '@asset-management/app-shell/layout';
import { pluginRegistry } from '@asset-management/app-shell/plugin';
import { HELP_TOPICS } from '../help/topics';

const MENU_LABEL_REFRESH_EVENT = 'atrm:menu-label-refresh';

export const applicationLayout = {
  title: 'Модуль финансового моделирования и оценки рисков',
  subtitle: 'Расчёт P&L, Cash Flow, производного баланса и стохастической оценки финансовых рисков.',
  expandSidebarLabel: 'Развернуть меню',
  collapseSidebarLabel: 'Свернуть меню',
  help: { topics: HELP_TOPICS },
  navigation: {
    registry: pluginRegistry,
    prependItems: [
      {
        path: '/',
        label: 'Главная',
        icon: <HomeOutlined />,
      },
    ],
    defaultOpenKeys: ['/valuations', '/dashboard'],
    labelRefreshEvents: [MENU_LABEL_REFRESH_EVENT],
    refreshLabelsOnStorage: true,
  },
} satisfies ApplicationLayoutProps;
```

В `web` принадлежат:

- title/subtitle приложения;
- Home item;
- business help topics;
- default expanded menu groups;
- app-specific label refresh events;
- optional app-specific header actions.

Shell владеет:

- layout geometry;
- sider collapse/expand;
- delayed hover preview;
- route-aware navigation;
- standard Help button;
- standard user menu;
- plugin-menu rendering.

---

# 10. Routing

Для standard application используйте:

```ts
import { createStandardApplicationRouter } from '@asset-management/app-shell/routing';
```

Пример:

```tsx
const router = createStandardApplicationRouter({
  layout: applicationLayout,
  homeElement: <HomePage />,
  routes: moduleRoutes,
});
```

Shell строит:

```text
/login

ApplicationAuthBoundary
  └── ApplicationLayout
        ├── index -> HomePage
        └── plugin routes
```

Используйте `createApplicationRouter()` только если приложению действительно нужен custom login/auth/layout, но вы хотите сохранить остальные routing helpers shell.

---

# 11. Lazy routes и RouteSuspense

Используйте shell `RouteSuspense` вместо локальных копий `<Suspense fallback=...>`.

```tsx
import { lazy } from 'react';
import { RouteSuspense } from '@asset-management/app-shell/routing';

const Page = lazy(() => import('./pages/Page'));

const element = (
  <RouteSuspense>
    <Page />
  </RouteSuspense>
);
```

Custom fallback допустим, если для конкретной страницы он имеет UX-смысл:

```tsx
<RouteSuspense fallback={<PageSpecificSkeleton />}>
  <HeavyPage />
</RouteSuspense>
```

Не создавайте очередной generic `SuspensePage` внутри business module.

---

# 12. Plugin architecture

Каждый feature module в:

```text
web/src/modules/<module>/
```

является plugin.

Рекомендуемая структура:

```text
<module>/
├── index.tsx
├── menu.tsx
├── pages/
├── components/
├── store/
├── hooks/
└── styles.css
```

Не все директории обязательны.

---

## 12.1 ModuleRegistration

Current contract:

```ts
interface ModuleRegistration {
  enabled?: boolean;
  menu: MenuItem[];
  routes: () => RouteObject[];
  registerContributions?: (
    registry: PluginRegistryContract,
  ) => void;
}
```

Пример:

```tsx
import type { ModuleRegistration } from '@asset-management/app-shell/plugin';
import { ApplicationPermissionGuard } from '@asset-management/app-shell/auth';
import { RouteSuspense } from '@asset-management/app-shell/routing';
import { lazy } from 'react';

import menu from './menu';

const RunPage = lazy(() => import('./pages/RunPage'));
const HistoryPage = lazy(() => import('./pages/HistoryPage'));

const routes: ModuleRegistration['routes'] = () => [
  {
    path: '/example/run',
    element: (
      <RouteSuspense>
        <ApplicationPermissionGuard
          permission={{ resource: 'example', action: 'run' }}
        >
          <RunPage />
        </ApplicationPermissionGuard>
      </RouteSuspense>
    ),
  },
  {
    path: '/example/history',
    element: (
      <RouteSuspense>
        <HistoryPage />
      </RouteSuspense>
    ),
  },
];

export default {
  enabled: true,
  menu,
  routes,
} satisfies ModuleRegistration;
```

`enabled: false` отключает регистрацию menu, routes и contributions.

---

## 12.2 Menu metadata

Пример:

```tsx
import { FundProjectionScreenOutlined } from '@ant-design/icons';
import type { MenuItem } from '@asset-management/app-shell/plugin';

const menu: MenuItem[] = [
  {
    path: '/example',
    label: 'Example',
    icon: <FundProjectionScreenOutlined />,
    children: [
      {
        path: '/example/run',
        label: 'Run',
        permission: {
          resource: 'example',
          action: 'run',
        },
      },
      {
        path: '/example/history',
        label: 'History',
      },
    ],
  },
];

export default menu;
```

Shell:

- recursively фильтрует items по permissions;
- удаляет parents без видимых children;
- resolve-ит dynamic labels;
- определяет current-route selection;
- выполняет navigation.

Business module должен отдавать metadata, а не реализовывать sidebar.

---

## 12.3 Dynamic labels

`MenuItem` может содержать:

```ts
getLabel?: () => ReactNode;
```

Приложение может настроить `labelRefreshEvents` и/или `refreshLabelsOnStorage`.

Название event — application policy и остаётся в `web`; listener mechanics принадлежит shell.

Не hard-code ATRM event names внутри `app-shell`.

---

# 13. Plugin autodiscovery

Physical discovery остаётся в consuming Vite application, потому что `import.meta.glob` должен быть statically analyzable именно там.

Правильный pattern:

```ts
const moduleImports = import.meta.glob<ModuleRegistration>(
  '/src/modules/*/index.tsx',
  {
    import: 'default',
    eager: false,
  },
);
```

**Важно:** не используйте alias как prefix glob:

```ts
// Неправильно
import.meta.glob('@modules/*/index.tsx');

// Правильно
import.meta.glob('/src/modules/*/index.tsx');
```

Glob должен начинаться с `/` или `./`.

Далее registration semantics передаётся shell:

```ts
const moduleRoutes = await registerDiscoveredModules({
  moduleImports,
  registry: pluginRegistry,
});
```

---

# 14. Generic plugin contributions

PluginRegistry в shell не зависит от state manager.

Основной API:

```ts
registry.registerContribution(slot, key, value);
```

и:

```ts
registry.getContributions<T>(slot);
```

Не добавляйте `registerZustandSlice()` или `StateCreator` в shell contracts.

---

## 14.1 Zustand contribution adapter в текущем web

Текущее приложение определяет slot:

```ts
export const ZUSTAND_SLICE_CONTRIBUTION = 'web:zustand-slice';
```

и helpers:

```ts
registerZustandSlice(registry, key, slice);
getRegisteredZustandSlices(pluginRegistry);
```

Business plugin может зарегистрировать state:

```ts
const registerContributions: ModuleRegistration['registerContributions'] = (registry) => {
  registerZustandSlice(registry, 'calculations', createCalculationSlice);
};
```

Application initialization интерпретирует contribution до создания store.

Такая модель позволяет App2 использовать тот же shell с:

- Redux reducers;
- service registrations;
- widgets;
- command definitions;
- другим state manager;

без изменения shell.

---

# 15. Порядок инициализации store

Критический invariant текущего приложения:

```text
1. discover plugins
2. register plugin menu/routes/contributions
3. read web:zustand-slice contributions
4. initialize Zustand store
5. create router
6. render application
```

Не создавайте dynamic store до регистрации module contributions.

Текущий router composition должен сохранять этот порядок.

---

# 16. Contextual Help

Механика Help принадлежит shell; business content принадлежит приложению.

Shell API:

```ts
import type { HelpTopic } from '@asset-management/app-shell/help';
```

Application topics:

```ts
import calculationRun from './docs/calculation-run.md?raw';
import type { HelpTopic } from '@asset-management/app-shell/help';

export const HELP_TOPICS: HelpTopic[] = [
  {
    id: 'calculation-run',
    title: 'Запуск расчётов',
    route: '/calculations/run',
    content: calculationRun,
  },
];
```

Далее в application layout:

```ts
help: {
  topics: HELP_TOPICS,
}
```

Shell владеет:

- Help button;
- drawer state;
- route-to-topic resolution;
- markdown rendering;
- `help:` topic links;
- empty state.

Business application владеет:

- topic IDs;
- route mappings;
- markdown content;
- business terminology.

Topic без `route` всё равно может быть доступен через `help:<topic-id>` ссылку из другого help-документа.

---

# 17. MainFormLayout

Для новых standard full-page forms используйте:

```tsx
import { MainFormLayout } from '@asset-management/app-shell/layout';

<MainFormLayout
  title="Редактирование контракта"
  header={<Breadcrumbs />}
  actions={<FormActions />}
>
  <ContractForm />
</MainFormLayout>
```

Основные props:

```ts
interface MainFormLayoutProps {
  title: ReactNode;
  children: ReactNode;
  header?: ReactNode;
  actions?: ReactNode;
  padding?: CSSProperties['padding'];
  cardProps?: CardProps;
}
```

Не мигрируйте сложную существующую страницу только ради сокращения нескольких строк markup, если есть риск изменить layout или behavior.

Для новых standard form pages предпочитайте `MainFormLayout` вместо локальной реализации page shell.

---

# 18. State management conventions

Целевое разделение остаётся таким:

```text
Zustand          = client/UI state
TanStack Query   = server state
```

Zustand используйте для:

- selected entity IDs/slugs;
- UI filters;
- unsaved form drafts;
- local toggles / panel state;
- current auth/permission state приложения;
- legacy client state на период миграции.

TanStack Query используйте для:

- backend lists/details;
- reference dictionaries;
- calculation results;
- polling;
- cache/invalidation/refetch behavior.

Не добавляйте новые конструкции вида:

```text
fetchX
xLoading
xError
xData
```

в Zustand, если это обычный server-state use case.

Shell предоставляет `QueryClientProvider`; сами business queries принадлежат `web`.

---

# 19. Generated API

Backend API access остаётся application-owned.

Правила:

- generated OpenAPI client — canonical client приложения;
- generated API нельзя импортировать в `app-shell` или `ui-kit`;
- generated models нельзя вручную дублировать;
- новые server-state queries должны вызывать generated functions;
- HTTP auth/interceptors остаются в `web`, потому что зависят от конкретного backend contract.

Это позволяет App2/App3 использовать другой backend с тем же shell.

---

# 20. Создание нового business module

Рекомендуемый checklist:

1. Создать `web/src/modules/<module>/`.
2. Добавить `index.tsx` с `ModuleRegistration`.
3. Добавить `menu.tsx` с `MenuItem[]`.
4. Большие pages загружать через `lazy()`.
5. Оборачивать lazy pages в `RouteSuspense`.
6. Permission requirements объявлять в route/menu metadata.
7. Business CSS держать внутри module.
8. Новый server state реализовывать через TanStack Query.
9. Регистрировать только действительно необходимые application-specific contributions.
10. Не редактировать центральный список routes/menu — plugin должен обнаруживаться autodiscovery.

Минимальный пример:

```tsx
// modules/example/index.tsx
import type { ModuleRegistration } from '@asset-management/app-shell/plugin';
import { RouteSuspense } from '@asset-management/app-shell/routing';
import { lazy } from 'react';
import menu from './menu';

const ExamplePage = lazy(() => import('./pages/ExamplePage'));

export default {
  menu,
  routes: () => [
    {
      path: '/example',
      element: (
        <RouteSuspense>
          <ExamplePage />
        </RouteSuspense>
      ),
    },
  ],
} satisfies ModuleRegistration;
```

---

# 21. Создание App2 / App3

Новое standard application должно состоять в основном из configuration и business plugins.

Концептуальная структура:

```text
new-web/
├── src/
│   ├── app/
│   │   ├── application.tsx
│   │   ├── adapters/
│   │   │   ├── authAdapter.ts
│   │   │   └── permissionAdapter.ts
│   │   ├── home/
│   │   └── router/
│   ├── modules/
│   ├── help/
│   └── main.tsx
└── package.json
```

Шаги:

1. подключить `@asset-management/app-shell` и `@asset-management/ui-kit`;
2. описать application metadata;
3. реализовать `AuthAdapter`, если нужна authentication;
4. реализовать `PermissionAdapter`, если нужен permission-aware UI;
5. добавить business plugins;
6. объявить Vite `import.meta.glob('/src/modules/*/index.tsx')`;
7. зарегистрировать plugins;
8. обработать application-specific contributions/state;
9. вызвать `createStandardApplicationRouter()`;
10. вызвать `renderApplication()`.

Standard App2 не должен создавать свои копии:

```text
MainLayout
SideMenu
UserMenu
LoginPage
RequireAuth
RequirePermission
HelpDrawer
generic Suspense wrapper
```

если его UX намеренно не отличается от standard shell.

---

# 22. Когда расширять App Shell

Добавляйте capability в shell, когда одновременно выполняются условия:

1. App2/App3 иначе придётся повторно реализовать ту же mechanics.
2. Код не требует business entities или backend-specific types.
3. Различия приложений можно выразить через metadata или adapter.
4. Public contract осмыслен без знания текущего Zustand store.

Хорошие кандидаты:

- standard error boundary;
- standard 404/403 pages;
- notification infrastructure;
- application command palette mechanics;
- common application preferences infrastructure;
- generic audit/activity shell, если он реально нужен нескольким apps.

Плохие кандидаты:

- `ContractSelector`;
- valuation filters;
- GL account rules;
- domain calculations;
- ATRM permission vocabulary;
- generated core-service client.

---

# 23. Когда расширять UI Kit

Добавляйте компонент в UI Kit, если его reuse связан прежде всего с presentation/interaction semantics.

Хорошие кандидаты:

- generic `PageLoader`;
- generic feedback/empty components;
- generic numeric-input conventions;
- generic chart wrapper, если он не содержит financial semantics;
- reusable DataGrid extensions;
- reusable schema-form templates.

Если компоненту нужны routing, auth, plugins или application runtime, скорее всего это `app-shell`, а не `ui-kit`.

---

# 24. Типовые ошибки

## Ошибка: business state внутри shell

```ts
// Неправильно
import { useStore } from '@app/core';
```

внутри `app-shell`.

Решение: adapter contract.

---

## Ошибка: generated API внутри shell

```ts
// Неправильно
import { getContracts } from '@shared/api/generated/...';
```

Shell не должен знать backend текущего приложения.

---

## Ошибка: дублирование shell components в web

Не создавайте новый `SideMenu.tsx`, который только передаёт plugin metadata в `PluginSideNavigation`.

Передавайте metadata/configuration standard shell.

---

## Ошибка: alias внутри Vite glob

```ts
// Неправильно
import.meta.glob('@modules/*/index.tsx');

// Правильно
import.meta.glob('/src/modules/*/index.tsx');
```

---

## Ошибка: state-manager-specific plugin contract

Не добавляйте `StateCreator` в `ModuleRegistration`.

Используйте generic contribution slots и интерпретируйте их внутри приложения.

---

## Ошибка: global CSS в business application ради shell geometry

Viewport/sidebar/header mechanics принадлежат shell.

Module CSS принадлежит module.

---

## Ошибка: wrappers без смысла

Wrapper, который только переименовывает third-party component и не создаёт стабильный project-level contract, обычно не нужен.

Либо импортируйте библиотеку напрямую, либо создавайте wrapper только при наличии реальной reusable semantics.

---

# 25. Verification checklist

Перед merge изменений в shell/UI-kit:

```bash
cd frontend
npm ci
npm run build
```

Дополнительно проверить:

- `app-shell` не импортирует `web`, `@app`, `@modules`, `@shared`;
- в `app-shell` нет Zustand imports;
- в `app-shell` и `ui-kit` нет generated application API;
- Vite autodiscovery обнаруживает все plugins;
- plugin routes регистрируются до создания router;
- dynamic state contributions регистрируются до `initializeStore()`;
- permission-filtered menu работает как раньше;
- collapsed sidebar и hover preview не изменились;
- Help корректно определяется по current route;
- inaccessible routes показывают ожидаемый 403;
- App2-style standard configuration не требует custom layout wiring.

Для high-risk refactor сначала подтвердите behavioral parity, потом удаляйте compatibility code.

---

# 26. Сравнение с frontend-экосистемой 2026

Этот раздел отвечает на вопрос: есть ли в 2026 готовый framework или более современный архитектурный подход, который лучше текущей схемы `ui-kit + app-shell + web`.

## 26.1 Краткий вывод

Текущая архитектура **хорошо соответствует enterprise React-подходам 2026 года**:

- infrastructure capabilities подключаются через providers/adapters;
- business code отделён от application mechanics;
- navigation и modules описываются metadata, а не центральными hard-coded списками;
- server state постепенно уходит в Query, а не в global client store;
- reusable application foundation оформлен как package boundary;
- AI всё чаще строится через typed tools/capabilities, а не через один глобальный chatbot component.

Сильной причины переписывать текущий ETRM frontend на другой meta-framework нет.

Ближайшие готовые альтернативы по концепции:

- Refine;
- react-admin;
- Umi Max / Ant Design Pro.

Они подтверждают правильность наших provider/adapter идей, но привносят resource/CRUD/admin conventions, которые хуже подходят calculation-heavy ETRM.

Рекомендуемый подход:

```text
оставить текущий shell
+ заимствовать зрелые provider/capability patterns
+ отдельно модернизировать React/Vite
+ строить AI через tool/MCP boundaries
```

---

## 26.2 Refine

Refine — один из наиболее близких готовых вариантов для enterprise internal tools.

Он предоставляет provider contracts для:

- authentication;
- access control;
- data;
- routing;
- notifications;
- i18n;
- realtime/live data;
- audit logging.

Access-control model Refine с generic `can({ resource, action, params })` очень близок к нашим:

```text
AuthAdapter
PermissionAdapter
ApplicationCan
ApplicationPermissionGuard
```

### Где Refine сильнее из коробки

- больше standardized providers;
- CRUD/resource conventions;
- standard internal-tool workflows;
- audit/realtime/notification abstractions;
- готовая ecosystem.

### Почему текущий ETRM не стоит переписывать на Refine

ETRM — не обычная CRUD console. В нём есть:

- calculation launches и long-running workflows;
- simulation analysis;
- liquidity/risk screens;
- AG Grid-heavy tables;
- Plotly analytical pages;
- JSON-schema-driven domain forms;
- dynamic plugin contributions.

Переход на Refine заменит один platform layer другим, но большая часть custom infrastructure всё равно останется.

### Что стоит заимствовать

Идею completeness providers.

Если несколько applications реально потребуют capability, можно добавить:

```text
NotificationAdapter
AuditAdapter
I18nAdapter
RealtimeAdapter
```

Но не заранее — только при появлении второго реального consumer.

---

## 26.3 React-admin

React-admin также использует зрелую provider-модель, включая `authProvider` и `canAccess({ resource, action, record })`.

Он очень хорошо подходит для standard administrative CRUD applications.

Для текущего ETRM подходит хуже Refine, потому что ещё сильнее ориентирован на:

```text
list
create
edit
show
resource
```

Рекомендация:

```text
использовать react-admin как reference для auth/access API,
но не как migration target текущего ETRM
```

Для отдельного master-data/admin application его можно оценить отдельно.

---

## 26.4 Umi Max / Ant Design Pro

Umi Max предоставляет enterprise React application framework с:

- Ant Design;
- layout/menu;
- access control;
- initial state;
- request infrastructure;
- React Query integration;
- microfrontends;
- module federation;
- plugin architecture.

Это заметно пересекается с `app-shell`.

### Плюсы

- много enterprise plumbing уже реализовано;
- хорошая интеграция с Ant Design;
- mature layout/access conventions;
- plugin-oriented architecture.

### Почему не стоит мигрировать сейчас

Миграция заменит текущий Vite/router/bootstrap model и увеличит framework surface.

При этом business-specific plugin/state model всё равно придётся адаптировать.

Рекомендация:

```text
оставить Vite + app-shell;
использовать Umi Max как benchmark возможностей
```

Для нового простого Ant Design intranet application Umi Max можно рассматривать отдельно.

---

## 26.5 React Router Framework Mode

Современный React Router предлагает несколько режимов: Declarative, Data и Framework Mode.

Framework Mode добавляет:

- route modules;
- typed route APIs;
- code splitting;
- SPA/SSR/static strategies.

Текущее приложение использует data-router подход и собственный plugin route discovery.

Переход может дать более формальные route modules, но будет конфликтовать с текущей plugin-composition model.

Рекомендация:

- не мигрировать только потому, что Framework Mode новее;
- пересматривать при отдельном redesign routing;
- plugin discovery считать обязательным requirement при сравнении.

---

## 26.6 TanStack Start

TanStack Start — full-stack React framework на TanStack Router с SSR, streaming и server functions.

Для системы, где authoritative backend уже Python/FastAPI + Rust, integrated JS server functions дают значительно меньше пользы.

Рекомендация:

```text
не мигрировать текущий ETRM
```

TanStack Router отдельно может быть интересен для greenfield application, если критичны strongly typed navigation и typed search params.

---

## 26.7 React 19 и React Compiler

Текущий проект остаётся на React 18.3.1.

Это не архитектурная проблема.

Upgrade React нужно выполнять отдельно от extraction `app-shell`.

Рекомендуемый порядок:

```text
1. стабилизировать shell boundaries
2. отдельно обновить и протестировать React
3. отдельно оценить React Compiler
4. профилировать до удаления существующей memoization
```

React Compiler может быть полезен для data-heavy screens, но не исправляет:

- плохую state ownership;
- слишком широкие Zustand subscriptions;
- unstable props;
- ненужные global rerenders.

---

## 26.8 Vite 8

Vite 8 — современная stable линия Vite с Rolldown.

Для растущего multi-package frontend upgrade потенциально полезен, но должен быть самостоятельной migration-задачей.

Особенно важно отдельно протестировать:

```text
import.meta.glob
workspace source package resolution
generated client imports
MSW
production bundle
```

Не смешивайте major Vite upgrade с business refactor.

---

# 27. AI architecture в 2026

AI architecture постепенно сместилась от идеи:

```text
"добавим chatbot справа"
```

к модели:

```text
model
  + typed tools
  + structured outputs
  + approval gates
  + reusable resources/context
  + interoperable protocols вроде MCP
```

Для multi-purpose intranet platform это особенно важно.

---

## 27.1 Shell не должен зависеть от одного LLM vendor

Избегайте:

```text
app-shell -> OpenAI-specific business client
app-shell -> Anthropic-specific client
app-shell -> concrete model names
```

Если AI становится cross-application capability, нужен generic adapter contract или plugin contribution.

Концептуально:

```text
web/module
  └── AI capability metadata / tools
          ↓
     application AI adapter
          ↓
       AI runtime
```

Не вводите `AiAdapter`, пока действительно несколько applications не потребуют одинаковую shell-level AI experience.

---

## 27.2 MCP хорошо подходит для backend capabilities

Model Context Protocol хорошо ложится на exposed capabilities:

- tools;
- resources;
- prompts.

Для этой платформы это особенно полезно, потому что authoritative data и actions уже принадлежат backend.

Рекомендуемое направление:

```text
FastAPI / service layer
     ↓
controlled domain tools
     ↓
MCP server/gateway
     ↓
AI clients / agents / IDE assistants
```

Примеры потенциальных tools:

```text
get_valuation_run
compare_simulation_runs
query_liquidity_metrics
get_market_curve
create_calculation_run
explain_gl_account
```

Sensitive write tools должны использовать normal backend authorization и approval requirements.

MCP не заменяет application security.

---

## 27.3 AI tools должны описывать domain capabilities, а не UI automation

Предпочтительно:

```text
run_valuation(portfolio_id, observation_date, scenario)
```

а не:

```text
click_the_blue_run_button()
```

Первый вариант:

- стабилен;
- testable;
- usable headlessly;
- не зависит от DOM/layout.

UI/client tools уместны для безопасных локальных действий:

- navigate to route;
- select tab;
- populate filter;
- highlight result;
- open relevant help topic.

Business actions и data access должны оставаться server tools.

---

## 27.4 Approval flows

Современные AI SDK всё чаще поддерживают explicit approval / interrupt flows для tool execution.

Это хорошо согласуется с требованием, что high-risk calculation/business actions не должны выполняться unattended.

Recommended invariant:

```text
read-only / explanatory tool
    -> может выполняться автоматически, если policy разрешает

state-changing / high-risk tool
    -> explicit approval + normal business authorization
```

Approval нельзя реализовывать только в React UI. Где требуется security/business enforcement, его должен проверять server/tool layer.

---

## 27.5 TanStack AI

TanStack AI — provider-agnostic type-safe AI toolkit с React integration, streaming, typed tools и approval flows.

Он хорошо соответствует текущему TypeScript/TanStack mindset.

Но оценивать его следует внутри AI feature module, а не делать обязательной dependency `app-shell`.

Возможный layout:

```text
web/modules/ai
  ├── chat UI
  ├── streaming client
  ├── typed client tools
  └── tool approval UX
```

Authoritative server tools при этом остаются за backend/MCP/API boundary.

---

## 27.6 Vercel AI SDK

Vercel AI SDK — ещё один сильный вариант для streaming/tool-based AI UI.

Выбор между:

- TanStack AI;
- Vercel AI SDK;
- thin custom SSE/WebSocket client;

следует делать внутри AI module с учётом:

- Python backend compatibility;
- streaming protocol;
- tool/approval requirements;
- provider independence;
- structured outputs;
- operational constraints.

Shell не должен зависеть от этого выбора.

---

## 27.7 MCP Apps и agent-compatible UI

Важный тренд — business capability остаётся полезной без UI, а UI является одной из projections.

Полезный принцип:

```text
business capability first
UI projection second
```

Например valuation comparison в перспективе должен быть доступен:

- обычному React application;
- AI assistant;
- IDE/agent через MCP;
- возможно интерактивному MCP-compatible UI.

React `web` остаётся самым богатым first-party UX, но business capabilities не должны быть спрятаны внутри React event handlers.

---

# 28. Рекомендуемый roadmap

## P0 — стабилизировать текущую архитектуру

Не выполнять ещё один широкий architecture migration сразу.

Текущая boundary выглядит правильно:

```text
ui-kit       presentation
app-shell    application mechanics
web          business application
```

---

## P1 — reliability hardening

Рекомендуемые небольшие задачи:

1. Self-host Inter или перейти на approved system font stack.
2. Убедиться, что `QueryClient` lifecycle привязан к application instance, если появятся multiple roots/tests.
3. Упростить provider composition, если осталась избыточная вложенность.
4. Добавить standard 404/error boundary behavior.
5. Добавить тесты на `PluginRegistry`, permission filtering, help route resolution и standard router creation.

---

## P2 — platform maturity

Только после появления App2 оценить реально повторяющиеся capabilities:

```text
NotificationAdapter
AuditAdapter
I18nAdapter
RealtimeAdapter
ApplicationPreferences adapter
Command palette
```

App2 должен быть эмпирической проверкой того, что действительно должно жить в shell.

---

## P3 — dependency modernization

Выполнять независимо:

```text
React 18 -> React 19
React Compiler adoption
Vite 5 -> Vite 8
router major-version upgrade
AG Grid major upgrades
Ant Design upgrades
```

Не объединять всё это с business feature migration.

---

## P4 — AI-native capability layer

Если AI становится общей возможностью для нескольких applications:

1. описывать backend domain capabilities как typed tools;
2. использовать MCP как кандидат для interoperable tools/resources/prompts;
3. сохранять approval для dangerous actions;
4. использовать TanStack AI / Vercel AI SDK внутри AI module;
5. вводить shell-level `AiAdapter` только если нескольким apps нужен одинаковый global AI surface;
6. использовать plugin contributions для metadata о capabilities, но не для обхода server authorization.

Возможная architecture:

```text
business services / FastAPI / Rust
          │
          ├── REST/OpenAPI
          └── MCP tools/resources
                   │
            AI runtime / gateway
                   │
      ┌────────────┴────────────┐
      │                         │
web AI module             external AI hosts
      │
optional shell AI surface
```

---

# 29. Build-vs-adopt matrix

| Вариант | Fit для текущего ETRM | Основной плюс | Основная цена | Рекомендация |
|---|---:|---|---|---|
| Current UI Kit + App Shell | Высокий | Точный fit, controlled boundaries, plugin model | Поддерживать небольшой свой platform layer | **Оставить** |
| Refine | Средне-высокий | Mature provider architecture и internal-tool primitives | Resource/CRUD assumptions, migration | Заимствовать patterns, не переписывать |
| React-admin | Средний | Отличные admin/resource workflows и access control | Сильная admin CRUD model | Рассматривать для отдельного admin app |
| Umi Max / Ant Design Pro | Средне-высокий | Готовый enterprise AntD shell/plugins/access | Большой framework ownership/migration | Benchmark, не текущая миграция |
| React Router Framework Mode | Средний | Route modules/types/code splitting | Конфликт с текущей plugin route composition | Только при redesign routing |
| TanStack Start | Низко-средний | Full-stack typed React framework | Дублирует часть Python backend responsibilities | Не мигрировать |
| Next.js | Низко-средний | Большая full-stack/SSR ecosystem | Ненужный JS server layer | Не мигрировать |
| TanStack AI | Высокий для AI module | Type-safe streaming/tools/approval | Новая быстро развивающаяся dependency | Оценить внутри AI module |
| Vercel AI SDK | Высокий для AI module | Mature streaming/tool ecosystem | Integration choices | Оценить внутри AI module |
| MCP | Высокий для platform AI tools | Cross-client standard для tools/resources/prompts | Требует tool/API design и governance | **Сильный стратегический кандидат** |

---

# 30. Финальные engineering rules

Эти invariants должны быть видимы в code review:

```text
1. web — business-first.

2. app-shell не зависит от конкретного state manager.

3. ui-kit не зависит от application mechanics.

4. plugins описывают business modules; shell их hosting/runtime.

5. business permissions — application policy;
   permission mechanics — shell behavior.

6. auth implementation принадлежит application;
   standard auth UX — shell.

7. server state принадлежит TanStack Query.

8. generated backend clients не попадают в shell/ui-kit.

9. Vite import.meta.glob остаётся в consuming application.

10. generic contributions предпочтительнее technology-specific plugin API.

11. новая shared capability попадает в shell только после реального multi-app reuse.

12. AI tools описывают business capabilities, а не DOM/button automation.

13. sensitive AI actions используют normal backend permissions и approval policy.

14. major dependency upgrades отделены от business refactoring.
```

---

# 31. Короткий onboarding path

Новому разработчику рекомендуется изучать frontend в таком порядке:

```text
1. frontend/README.md
2. этот Developer Guide
3. web/AGENTS.md
4. web/src/app/application.tsx
5. web/src/main.tsx
6. web/src/app/router/index.tsx
7. один простой module/index.tsx + menu.tsx
8. app-shell public exports
9. ui-kit public exports
10. только нужный business module
```

Для обычной feature-разработки разработчику редко нужно менять `app-shell` или `ui-kit`.

Типовая business-задача должна в основном оставаться внутри:

```text
web/src/modules/<domain>/
```

Любое изменение platform layer (`app-shell` / `ui-kit`) должно рассматриваться как осознанная architectural change.
