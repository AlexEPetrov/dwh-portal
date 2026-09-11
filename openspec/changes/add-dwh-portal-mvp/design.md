# Design: add-dwh-portal-mvp

## Routing

- `AGENTS.md`
- `backend/core-service/AGENTS.md`
- `frontend/web/AGENTS.md`
- `rules/README.md`
- `rules/policy.yaml` topics `catalog`, `ingestion`, `http-api-contract`
- workflow `SPEC-WF-API-CONTRACT`
- contract `http-api`

## Authoring / published / generated

| Role | Path |
|---|---|
| authoring source | `backend/core-service/src/api/portal/**` |
| published contract | `common/contracts/openapi/openapi.json` |
| generated consumer | `frontend/web/src/shared/api/generated/**` |
| consumer | `frontend/web/src/modules/catalog/**` |

## Runtime shape

Существующий `core-service` остаётся HTTP-хостом. Новый домен
`domains/catalog` держит каноническую модель, репозиторий снимков,
провайдеры и коллекторы. FastAPI монтирует `/api/v1`.

UI читает только сгенерированный клиент. Коллекторы не запускаются
страницей: память/SQL store наполняется seed для прототипа и
идемпотентными коллекторами, которые Airflow сможет вызывать через
`run_daily_collection()`.

## Compatibility

`additive_compatible` относительно текущего OpenAPI: добавляются новые
пути `/api/v1/*`, существующие `/api/management|valuation|...` не
меняются.

## Verification IDs

- `CORE-PYTEST-TARGET` для `tests/unit/test_catalog`
- `OPENAPI-EXPORT`
- `FRONTEND-GEN-API`
- `FRONTEND-BUILD`

## Human approval checkpoint

Семантика API и канонической модели взята из ADR без альтернативного
выбора. Если при реализации появится неоднозначность, не покрытая ADR,
работа останавливается как `UNRESOLVED_AUTHORITY`.
