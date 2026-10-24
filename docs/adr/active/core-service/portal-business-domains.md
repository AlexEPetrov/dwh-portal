# ADR: Бизнес-домены DWH Portal в `src/domains` (DDD-style)

## Status

Accepted

Updated: 2026-10-24

## Context

В UI уже есть три продуктовые зоны с разным смыслом и разной ценой ошибки:

- **Каталог** — чтение снимков: объекты, storage, lineage, changes;
- **Документы** — операционная загрузка файлов («Загрузить документ»);
- **Администрирование** — мутация конфигурации док-источников в реестре ETL.

Каноническое правило: **бизнес-домены реализуются в
`backend/core-service/src/domains/<domain>/` в стандартной, близкой к DDD
манере** — по образцу уже сложившегося `domains/catalog`.

Портал — единая точка входа к UI и задачам администрирования, части
мониторинга и минимальному стабильному каталогу. Существующий ingestion
registry остаётся рабочим механизмом; переход на OpenMetadata или аналог
возможен в будущем без установленного срока.

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

### 5. Логическая схема, выполнения и активность

`catalog` владеет логическими объектами и зависимостями: source → handler →
TABLE/VIEW. Определения registry, AST и явные metadata-контракты наполняют
схему независимо от конкретного запуска. Настройки ingestion редактируются
через `admin` в registry, а не в дублирующей каталожной конфигурации.

Мониторинг выполнений читает сведения о запусках, ошибки и пофайловый журнал
`sys.log_files`. Это не то же самое, что `documents`: последний отвечает за
приём пользовательского документа, а не за всю историю ETL. Переход к
загрузкам доступен из источника/процесса/объекта через явные ссылки.

При добавлении OpenLineage исходные события и проекция выполнений хранятся
отдельно от логического каталога и ссылаются на его объекты. Физическое имя
будущего модуля и границы API уточняются в implementation change; новый
микросервис или отдельное приложение этим ADR не предписываются.

Аналитика пользовательской активности на основе `g_audit` развивается
независимо от ingestion monitoring и каталога. Общая связь с объектами DWH
допустима; зависимость от наличия OpenLineage или OM не требуется.

### 6. Legacy `management`

`domains/management` и `/api/management/**` не являются home для админки
портала и в этом решении не переименовываются.

## Consequences

- Новая write/upload функциональность создаётся в `domains/admin` или
  `domains/documents` со своими `models` / `services` / `repositories`, а не
  добавляется в `domains/catalog`.
- Lineage collectors/adapters логической схемы остаются в `catalog`:
  это построение read-модели. Архив событий и модель конкретных выполнений
  отделяются от неё при реализации мониторинга.
- Пока write API нет, домены содержат каркас слоёв; поведение фиксируется в
  `openspec/specs/**` при реализации.

## Related

- `docs/adr/active/ADR-002-mvp-metadata-lineage.md`
- `docs/adr/active/DWH-Portal-Architecture-and-Design.md`
- `docs/adr/active/core-service/lineage-collection-adapters.md`
- `docs/adr/active/frontend/portal-frontend-modules.md`
