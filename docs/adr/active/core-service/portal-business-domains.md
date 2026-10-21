# ADR: Бизнес-домены DWH Portal в `src/domains` (DDD-style)

## Status

Accepted

## Context

В UI уже есть три продуктовые зоны с разным смыслом и разной ценой ошибки:

- **Каталог** — чтение снимков: объекты, storage, lineage, changes;
- **Документы** — операционная загрузка файлов («Загрузить документ»);
- **Администрирование** — мутация конфигурации док-источников в реестре ETL.

На фронтенде меню разделено, но код жил в одном модуле `catalog`. На бэкенде
весь портал был в `domains/catalog`, а legacy-пакет `domains/management` не
является админкой портала.

Каноническое правило: **бизнес-домены реализуются в
`backend/core-service/src/domains/<domain>/` в стандартной, близкой к DDD
манере** — по образцу уже сложившегося `domains/catalog`.

## Decision

### 1. Домены портала

```text
src/domains/
├── catalog/      # read-модель портала
├── documents/    # document intake / загрузка документов
├── admin/        # администрирование реестра док-источников
├── management/   # legacy CQRS shell (не админка портала)
└── common/       # общие примитивы, не продуктовая фича
```

| Домен | Владеет | Не владеет |
|---|---|---|
| `catalog` | каноническая read-модель, снимки, lineage adapters, Portal DB read API | запись в `sys.data_extraction_sources`, upload файлов |
| `documents` | приём документов, статусы загрузки, интеграция с storage/inbox | редактирование реестра extraction sources |
| `admin` | write-операции над конфигурацией док-источников и смежный admin API | пользовательский browse каталога |

### 2. Внутренняя раскладка домена (DDD-lite)

Каждый бизнес-домен следует одной схеме слоёв (как `catalog`):

```text
domains/<domain>/
├── models.py | models/     # сущности, value objects, enum домена
├── services/               # application services / use-cases
├── repositories/           # ports + adapters к persistence
├── providers/              # опционально: внешние системы (DWH, S3, registry)
├── runtime.py              # composition root домена (wiring сервисов)
└── __init__.py
```

Правила:

- HTTP/API (`src/api/**`) тонкий: валидация входа, DTO, вызов domain service;
- доменная логика и инварианты живут в `domains/<domain>/`, не в роутерах;
- домены не импортируют друг друга «вглубь» (внутренние модули). Допустимы
  явные application-level зависимости через публичные сервисы/ports
  (например `admin` читает канонический `Asset` через catalog service);
- инфраструктура БД/миграций остаётся в `infrastructure/**`, домен зависит от
  ports, а не от SQLAlchemy-моделей напрямую, где это уже принято в `catalog`.

### 3. Границы API

```text
/api/v1/...                 # catalog (tag: catalog)
/api/v1/documents/...       # documents (tag: documents)
/api/v1/admin/...           # admin (tag: admin)
```

Catalog остаётся источником канонических `Asset` / `Relationship` для чтения.
Admin и documents не расширяют каталожный контракт сырыми ETL JSON как
основной моделью списка.

### 4. Frontend

Каждому бизнес-домену соответствует FE-модуль
`frontend/web/src/modules/<domain>/`. Меню «Администрирование» и «Документы»
не размещаются в модуле `catalog`.

### 5. Legacy `management`

`domains/management` и `/api/management/**` не являются home для админки
портала и в этом решении не переименовываются.

## Consequences

- Новая write/upload функциональность создаётся в `domains/admin` или
  `domains/documents` со своими `models` / `services` / `repositories`, а не
  добавляется в `domains/catalog`.
- Lineage collectors/adapters остаются в `catalog`: это построение read-модели.
- Пока write API нет, домены содержат каркас слоёв; поведение фиксируется в
  `openspec/specs/**` при реализации.

## Related

- `docs/adr/active/ADR-002-mvp-metadata-lineage.md`
- `docs/adr/active/DWH-Portal-Architecture-and-Design.md`
- `docs/adr/active/core-service/lineage-collection-adapters.md`
- `docs/adr/active/frontend/portal-frontend-modules.md`
