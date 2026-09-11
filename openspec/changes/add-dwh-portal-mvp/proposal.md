# Change: add-dwh-portal-mvp

## Summary

Реализовать Phase 1 DWH Portal на существующем каркасе
`backend/core-service` и `frontend/web` в соответствии с ADR
`docs/design/adr/active/DWH-Portal-Architecture-and-Design.md` и
`docs/design/adr/active/ADR-002-mvp-metadata-lineage.md`.

## Why

В репозитории есть прототип FastAPI/React, но нет канонического каталога
DWH, снимков хранения, source-to-DWH lineage и отслеживания структурных
изменений. Пользовательский запрос явно берёт эти ADR в работу.

## Capability map

Объявленные capabilities в `openspec/capabilities.yaml`:

- `catalog` — просмотр каталога, карточка объекта, storage/lineage/changes UI и Portal API чтения;
- `ingestion` — коллекторы, снимки, диагностика, детектор изменений.

Новых capability paths не создаётся.

## Changed scopes

- `openspec/specs/catalog/**`, `openspec/specs/ingestion/**`
- `backend/core-service/src/domains/catalog/**`
- `backend/core-service/src/api/portal/**` → публичный `/api/v1/*`
- `backend/core-service/src/infrastructure/db/models/portal.py`
- `frontend/web/src/modules/catalog/**`
- `frontend/web/src/app/**` (название приложения, home/overview, permissions)
- reconciliation: `common/contracts/openapi/openapi.json`,
  `frontend/web/src/shared/api/generated/**`

## Change types

- `business_or_contract_semantic`
- `public_api_semantic`

## Applicable routing

- topics: `catalog`, `ingestion`, `http-api-contract`
- workflow: `SPEC-WF-API-CONTRACT`
- contract: `http-api`
- `approval_policy`: `human_required` по классу публичного API и
  бизнес-семантики

## Approval

Семантика Phase 1 зафиксирована действующими ADR и явным поручением
пользователя реализовать проект по этим ADR. Новые семантики сверх ADR
не выбираются.

После этой фиксации механическая реализация, публикация OpenAPI,
генерация клиента и UI-потребители продолжаются без повторного выбора
контракта.

## Downstream

```text
FastAPI /api/v1
-> OPENAPI-EXPORT
-> common/contracts/openapi/openapi.json
-> FRONTEND-GEN-API
-> frontend/web/src/shared/api/generated/**
-> frontend catalog consumers
-> FRONTEND-BUILD
```
