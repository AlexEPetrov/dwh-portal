# docs/ — индекс внутренней документации

Status: Accepted  
Entry for agents/humans. Deep rules: [`documentation-policy.md`](documentation-policy.md).

**Load rule:** для ordinary edits в существующем файле достаточно этого index.  
Полный `documentation-policy.md` читать только при **создании, переносе, смене
типа** документа или сомнении «куда класть».

## Слои (не смешивать)

| Путь | Вопрос |
|---|---|
| `openspec/specs/**` | Что система делает сейчас? |
| `openspec/changes/**` | Что меняем? |
| `rules/**` | Как разрешено менять? |
| `AGENTS.md` | Как агенту работать? |
| `docs/**` | Почему / evidence / guides |

При расхождении: спека > ADR rationale > планы/guides.  
Governance ADR (`docs/adr/active/governance/**`) — cold rationale, не preload.

## Куда что в `docs/`

| Каталог | Назначение |
|---|---|
| `adr/active/`, `adr/superseded/` | Архитектурные решения (Nygard) |
| `adr/TEMPLATE.md` | Шаблон нового ADR |
| `plans/` | Крупные планы (после исполнения — декомпозиция) |
| `methodology/` | Методики расчётов/анализа |
| `technical/` | Технические объяснения, не контракт |
| `product/` | Product spine + maps для витрины |
| `generated/` | Производное; руками не править |
| `userguide/` | In-app справка |
| `issues/` | Только по необходимости |

## ADR (кратко)

- Заголовки EN: `Status` / `Context` / `Decision` / `Consequences`
- Статусы: `Proposed` \| `Accepted` \| `Superseded` (или `Draft`)
- Тело может быть на русском
- Superseded → файл в `adr/superseded/**` со ссылкой на новый
- На product-site: в теле теги  
  `Product-publish: yes` + `Product-capabilities: …`  
  (опционально `Product-summary:`); ищет `PRODUCT-DOCS-SYNC`

## Язык

Внутренние docs — русский. Исключения: заголовки/статусы ADR (EN),  
`AGENTS.md` (EN), идентификаторы кода/API не переводить.

## Дальше

Полные правила размещения, OpenSpec Purpose, generated files, product pipeline:  
[`documentation-policy.md`](documentation-policy.md).
