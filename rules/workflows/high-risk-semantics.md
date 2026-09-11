---
id: SPEC-WF-HIGH-RISK-SEMANTICS
status: active
authority: normative-workflow
applies_to:
  - backend/core-service/**
  - backend/calc-service/**
  - common/contracts/**
approval_policy: human_required
owners: []
approvers: []
last_reviewed: 2026-08-18
---

# Workflow: high-risk semantic changes

## Назначение

Этот workflow регулирует изменения, которые могут менять business/calculation semantics.

Он определяет **процесс изменения**, но не определяет сами business rules. Конкретная current semantics должна находиться в active governing spec.

## Когда workflow обязателен

Workflow активируется при behavior-affecting изменении хотя бы одной из областей:

- valuation semantics;
- filter semantics и contract selection;
- curve availability или calculation rules;
- date/period/interval interpretation, влияющей на расчёты;
- contract dependency ordering;
- shared Python↔Rust business/calculation behavior;
- nullable/empty/missing/default/fallback business semantics между boundaries;
- Excel financial/compatibility semantics;
- consumer-visible API semantics, если меняется business meaning.

Sensitive path сам по себе не доказывает semantic change.

```text
sensitive path touched
-> inspect semantic impact
```

Если behavior сохраняется, изменение может остаться `workflow_allowed` или получить другой policy через `ApplicableContext`.

Если intended business/calculation behavior меняется:

```text
approval_policy: human_required
```

## До human approval

Agent MAY:

- прочитать applicable routers/specs/design evidence;
- исследовать code и tests;
- сравнить Python/Rust behavior;
- определить затрагиваемые contracts/consumers;
- выявить drift/conflicts;
- подготовить proposal;
- подготовить candidate spec/ADR/code diff;
- предложить regression tests;
- перечислить migration/reconciliation consequences.

Agent MUST NOT:

- выбрать новую business/calculation semantics;
- считать proposal нормативным current behavior;
- реализовать semantic choice, который не был явно подтверждён;
- разрешить `SEMANTIC_CONFLICT` или `UNRESOLVED_AUTHORITY` самостоятельно.

## Approval checkpoint

Перед semantic implementation необходимо зафиксировать:

```text
topic
current governing spec/evidence
proposed semantic change
affected scopes
affected contracts/consumers
required approver
approval decision
```

Human approval относится к **intended semantics**, а не к каждой механической операции реализации.

После approval agent может автономно выполнить согласованную mechanical implementation, regeneration, reconciliation и verification.

Если появляется новая semantic ambiguity, gate открывается заново.

## Spec reconciliation

### Active spec существует

1. Изменить active governing spec так, чтобы он точно описывал approved intended behavior.
2. Сохранить stable requirement IDs или корректно добавить новые.
3. Не смешивать target proposal с current normative requirements после activation.

### Active spec отсутствует

1. Собрать registered governing evidence candidates через `rules/README.md`.
2. Сравнить design docs, code, tests, contracts и cross-service implementation.
3. Зафиксировать `SEMANTIC_CONFLICT`, если evidence расходится.
4. Получить human decision по intended/current behavior.
5. Создать proposed spec.
6. Перевести её в `active` только после required approval.

Старый design note не становится normative автоматически.

## Architecture decision

Создать или обновить ADR, если изменение:

- меняет service/boundary responsibility;
- меняет architecture contract;
- вводит новый compatibility model;
- меняет долгосрочную dependency/transport architecture;
- является решением, rationale которого важно сохранить отдельно от current-state spec.

ADR хранит rationale. Current operational rules должны находиться в governing spec.

## Cross-service parity

Если behavior объявлен shared между Python и Rust:

1. определить обе реализации;
2. проверить approved semantics на обеих сторонах;
3. обновить обе реализации, если это требуется;
4. выполнить targeted parity verification;
5. не закрывать task при silent parity gap.

Temporary parity gap допустим только как явно approved exception с:

```text
scope
reason
owner
expiration/review condition
expected convergence
```

## Contract reconciliation

Если semantic change затрагивает contract boundary:

1. определить authoring source;
2. изменить authoring source;
3. обновить source-side tests;
4. regenerate published contract;
5. regenerate generated consumers;
6. проверить affected consumers;
7. выполнить boundary-specific workflow.

Generated artifact вручную не редактируется.

## High-risk verification

Behavior-affecting high-risk change требует targeted regression evidence, которое проверяет **approved semantics**.

Не использовать формулировку "есть тест" как доказательство: должна быть зафиксирована выполненная команда и результат.

### Valuation / filters

Где применимо, проверить:

- empty filters;
- non-empty filters;
- nullable dimensions;
- include/exclude behavior;
- пересечения условий;
- scope/date boundaries;
- dependency ordering.

Sensitive symbols/areas include:

```text
backend/core-service/src/domains/risk/commands/mappings.py
build_valuation_request_model()
```

Конкретные field semantics должны находиться в governing spec.

### Curve / date behavior

Где применимо, проверить:

- month/day boundaries;
- stale `report_date`;
- stale observation date;
- point availability boundaries;
- fallback/absence behavior;
- Python↔Rust parity.

Sensitive areas include:

```text
backend/core-service/src/domains/risk/repositories/curve_data.py
backend/core-service/src/domains/risk/repositories/calendar_data.py
backend/core-service/src/domains/risk/services/valuation/local/calculators/curve_calculator.py
backend/core-service/src/domains/risk/services/valuation/local/calculators/index_calculator.py
```

Known semantic symbols that must be routed to the governing curve spec rather than defined here:

```text
point_interval
report_date_aheads
observ_date_aheads
CurveElement.aggregation
```

## Conflict handling

- `SEMANTIC_CONFLICT` -> stop semantic implementation, collect evidence, obtain human/owner decision.
- `UNRESOLVED_AUTHORITY` -> analysis/proposal allowed; semantic activation/implementation blocked.
- `MISSING_EVIDENCE` -> run required verification or record explicit blocker.
- `DRIFT` -> identify upstream source, regenerate/reconcile, verify.
- `BROKEN_ROUTING` -> stop semantic editing and fix routing first.

## Definition of done

High-risk semantic work is complete only when:

- intended semantics were explicitly approved;
- governing active spec describes current implemented behavior;
- applicable ADR rationale is updated where needed;
- required implementations are reconciled;
- shared Python↔Rust parity is verified where applicable;
- authoring/published/generated contracts are reconciled;
- targeted regression evidence was executed;
- affected API/Excel/frontend consumers were checked;
- no unrecorded semantic ambiguity remains;
- unresolved gaps are explicitly recorded as blockers/approved exceptions.
