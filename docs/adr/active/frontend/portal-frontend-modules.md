# ADR: Самодостаточные FE-модули с авто-discovery

## Status

Accepted

## Context

Sidebar уже разделяет продуктовые зоны, но код жил в одном
`modules/catalog`. В app-shell изначально заложен другой контракт: модули
самодостаточны и подхватываются автоматически через Vite
`import.meta.glob`, без ручной регистрации в роутере приложения.

## Decision

### 1. Один каталог = один модуль

```text
frontend/web/src/modules/
├── assistant/    # Ассистент (stub)
├── catalog/      # Overview, Objects, Storage, Lineage, Changes
├── documents/    # Загрузить документ
└── admin/        # Редактировать док-источники
```

Модуль самодостаточен и экспортирует `ModuleRegistration`:

```text
modules/<name>/
├── index.tsx     # default export: enabled, menu, routes, contributions?
├── menu.tsx
├── pages/
├── components/   # только внутренности модуля
└── store/        # опционально, Zustand slice модуля
```

Добавление модуля = появление `src/modules/<name>/index.tsx`. Явно править
список модулей в `app/router` не требуется.

### 2. Auto-discovery

Физический glob остаётся в приложении (ограничение Vite — glob должен быть
статически анализируем):

```ts
const moduleImports = import.meta.glob<ModuleRegistration>(
  '/src/modules/*/index.tsx',
  { import: 'default', eager: false },
);
```

Семантика регистрации — в app-shell `registerDiscoveredModules`:

- читает каждый `index.tsx`;
- пропускает `enabled: false`;
- добавляет `menu` в registry;
- собирает `routes()`;
- вызывает `registerContributions`, если есть.

### 3. Границы модулей

- модули не импортируют внутренности друг друга;
- общий presentation-код — в `src/shared/**` (например `@shared/ui/portal`);
- данные — только через generated API / shared client;
- admin menu несёт `permission: { resource: 'admin', action: 'edit' }`.

Соответствие backend-доменам (`src/domains`):

| FE module | BE domain |
|---|---|
| `catalog` | `domains/catalog` |
| `documents` | `domains/documents` |
| `admin` | `domains/admin` |
| `assistant` | future AI surface (не catalog) |

## Consequences

- Новый экран домена = файлы внутри его модуля; discovery подхватит сам.
- `catalog` больше не host для documents/admin/assistant.
- Стабильный порядок sidebar задаётся полем `order` в `ModuleRegistration`
  (`assistant` 10 → `catalog` 20 → `documents` 30 → `admin` 40); shell
  сортирует после discovery, ручной import модулей в роутере не нужен.

## Related

- `docs/adr/active/core-service/portal-business-domains.md`
- `frontend/web/AGENTS.md`
- `frontend/app-shell/USAGE.md`
- `frontend/web/src/app/router/index.tsx`
