---
id: SPEC-WF-EXCEL-COMPATIBILITY
status: active
authority: normative-workflow
applies_to:
  - backend/core-service/src/domains/management/services/office_interop/**
  - backend/core-service/src/api/**
  - backend/core-service/src/domains/risk/**
approval_policy: workflow_allowed
owners: []
approvers: []
last_reviewed: 2026-08-18
---

# Workflow: Excel import/export compatibility

## Назначение

Excel import/export является отдельным compatibility-sensitive interface layer.

Этот workflow определяет обязательную проверку Excel surface при изменениях, способных затронуть workbook structure, filters, exported/imported objects или user-visible semantics.

Он не определяет финансовую/business semantics. Если такая semantics меняется, применяется также `SPEC-WF-HIGH-RISK-SEMANTICS` и итоговый:

```text
approval_policy: human_required
```

## Когда workflow активируется

Активировать при:

- изменениях под `src/domains/management/services/office_interop/**`;
- изменении Excel exporter/importer behavior;
- изменении API/filter model, которое может быть представлено в XLSX;
- появлении нового structured filter;
- изменении management endpoints, связанных с Excel surface;
- изменении business field, которое экспортируется/импортируется;
- изменении compatibility behavior старых workbook formats.

Связанные changes могут активировать workflow даже без изменения самого Excel-кода.

## Approval policy

### Behavior-preserving mechanical change

Примеры:

- internal refactor;
- formatting implementation;
- logging;
- code cleanup без workbook/API semantic change.

Default:

```text
workflow_allowed
```

при условии, что verification подтверждает сохранение поведения.

### Semantic / compatibility change

Если меняется:

- financial meaning;
- field interpretation;
- workbook contract;
- import/export compatibility semantics;
- representation of filters/business dimensions;
- user-visible structured behavior,

то:

```text
human_required
```

и обязательно применяется `SPEC-WF-HIGH-RISK-SEMANTICS`.

## Impact analysis

Перед изменением определить:

```text
changed source
affected workbook surface
affected API/filter model
affected management endpoints
affected import path
affected export path
backward compatibility expectation
approval_policy
```

## Known compatibility touchpoints

Текущий repository evidence требует явно проверять, где применимо:

```text
backend/core-service/src/domains/management/services/office_interop/excel_exporter.py
ExcelExporter.export_objects()
```

Если API/filter semantics меняются, проверить, должен ли новый/изменённый structured field быть отражён:

- в XLSX export;
- в XLSX import;
- в листе `Инфо`;
- в служебных параметрах workbook;
- в связанных management endpoints.

Эти touchpoints являются routing/verification hints. Конкретная business semantics должна находиться в governing spec.

## Filter/model changes

При изменении:

```text
contract_filter
markets
products
gl_accounts
include/exclude
nullable dimensions
structured filters
```

не предполагать автоматически, что Excel unaffected.

Agent должен явно классифицировать Excel impact как:

```text
affected
not affected
unknown
```

`unknown` блокирует closeout, если изменение затрагивает public/business filter semantics.

## Compatibility expectations

Перед изменением определить, какая совместимость требуется:

- backward read compatibility;
- backward write compatibility;
- round-trip compatibility;
- same-version compatibility only;
- explicit migration/cutover.

Не выбирать compatibility policy самостоятельно, если она влияет на business/user behavior.

## Verification

В зависимости от change set проверить:

1. export создаёт ожидаемую структуру workbook;
2. import корректно читает ожидаемый supported format;
3. round-trip сохраняет required semantic fields;
4. новый/изменённый filter присутствует там, где это требуется governing spec;
5. лист `Инфо` и служебные параметры согласованы с изменением;
6. management/API surface не расходится с workbook representation;
7. nullable/empty/missing semantics не меняются скрыто;
8. старый supported workbook behavior не ломается без explicit approval.

Для semantic change verification должна проверять именно approved behavior.

## API interaction

Если Excel impact возник из API/filter change:

```text
API workflow
+
Excel compatibility workflow
```

Один workflow не заменяет другой.

Generated OpenAPI/client artifacts регулируются contract workflow и не редактируются вручную.

## Failure handling

Если необходимая Excel compatibility проверка невозможна:

```text
MISSING_EVIDENCE
```

и task не должен закрываться как полностью verified.

Если old/new workbook semantics расходятся и expected behavior не определён:

```text
SEMANTIC_CONFLICT
or
UNRESOLVED_AUTHORITY
```

в зависимости от причины.

## Definition of done

Excel-affecting change завершён, когда:

- Excel impact явно классифицирован;
- resolved `approval_policy` соблюдён;
- relevant export/import surfaces проверены;
- `ExcelExporter.export_objects()` проверен, если затронут;
- `Инфо`/service parameters проверены, если затронуты;
- API/filter model и Excel representation reconciled;
- backward compatibility requirement выполнен или явно изменён с approval;
- semantic changes прошли high-risk workflow;
- executed verification и remaining gaps зафиксированы.
