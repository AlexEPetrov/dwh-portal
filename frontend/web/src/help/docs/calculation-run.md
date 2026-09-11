# Запуск расчётов

Этот документ описывает экран `/calculations/run`.

## Назначение

Экран **Запуск расчётов** используется для старта valuation runs двух типов:

- **Детерминированный расчёт** — расчет без Monte Carlo sampling;
- **Монте-Карло симуляция** — расчет множества sample scenarios через calc-service.

После успешного запуска пользователь перенаправляется на историю расчетов, где можно смотреть статус и результаты запуска.

## Две вкладки

| Вкладка | Что запускает | Когда использовать |
|---|---|---|
| Детерминированный расчёт | Один valuation run по выбранным сценариям, датам и контрактному scope | Нужна базовая оценка, P&L, cash flow или отчет без распределения риска |
| Монте-Карло симуляция | Simulation run с заданным числом samples | Нужно получить распределение результатов и последующий risk analysis |

Обе вкладки используют похожую форму. Различие в том, что для Monte Carlo дополнительно задаются параметры sampling и parallel execution.

## Пресеты

В верхней части формы есть поле **Пресет**.

Пресет — сохраненный набор параметров запуска. При выборе пресета его параметры накладываются поверх текущей формы.

Бизнес-смысл пресетов:

- ускорить типовые запуски;
- стандартизировать параметры для регулярных расчетов;
- уменьшить риск ручной ошибки;
- сохранить agreed configuration для повторяемых сценариев.

Важно: пресет не является отдельным расчетом. Это только шаблон параметров, который заполняет форму перед отправкой.

## Основные группы параметров

Форма построена по JSON Schema, сгенерированной из backend Pydantic models. Группы и порядок полей задаются metadata в исходных моделях.

Типовые группы:

- **Даты** — valuation period и observation date;
- **Скоуп расчёта** — фильтр контрактов и атрибутов;
- **Параметры** — valuation type, engine, sampling options;
- **Отчеты** — период и настройки reporting output;
- **Перегрузка кривых** — curve overrides;
- **Отладка** — debug flags и debug pricing dates;
- **Другие** — сценарии и дополнительные системные параметры.

## Даты

Основные даты:

- `valuation_start_date` — начало периода оценки;
- `valuation_end_date` — конец периода оценки;
- `observation_date` — дата наблюдения, относительно которой берутся рыночные данные и simulation source.

`valuation_start_date` и `valuation_end_date` определяют, какие valuation periods попадут в расчет. `observation_date` определяет состояние входных данных на момент запуска.

## Сценарии

Поле `scenarios` выбирает набор сценариев, которые будут включены в запуск.

Если сценарии не выбраны или выбраны некорректно, расчет может быть пустым или не соответствовать ожидаемой бизнес-гипотезе.

## Contract filter

`contract_filter` ограничивает контракты, попадающие в расчет.

Поддерживаются два слоя:

- `contracts.include` / `contracts.exclude` — явное включение или исключение контрактов;
- `attributes` — фильтрация по business attributes, например markets, products, GL accounts.

Бизнес-смысл: contract filter задает scope расчета. Изменение scope считается изменением того, что именно оценивается.

## Reporting

Блок `reporting` задает настройки отчетов:

- `date_column` — колонка периода для отчетного разреза;
- `min_date` и `max_date` — отчетный интервал;
- `units` — настройки валюты, price unit и volume unit;
- amendments — дополнительные корректировки, если используются.

Reporting period может отличаться от valuation period. Это нормально: valuation period задает расчетную область, а reporting period задает представление результата в отчетах.

## Curve overrides

`curve_overrides` позволяет переопределить загрузку заданных кривых на заданном диапазоне дат.

Это high-risk параметр: он меняет входные market data для расчета. Его следует использовать только для явных сценариев, стресс-тестов или контролируемой отладки.

## Engine

`engine` определяет способ запуска.

Практический смысл:

- `service` — запуск через выделенный calc-service;
- `python` — legacy/local путь, если он поддерживается конкретным handler.

Для Monte Carlo текущая продуктивная семантика ориентирована на service/calc-service путь.

## Valuation type

`valuation_type` маркирует тип запуска и слой результатов. Примеры значений: `daily`, `eom`, `eoy`, UUID-like selector, `forecast`, `eod`.

Этот параметр важен для последующего чтения результатов: аналитические экраны и отчеты могут выбирать данные именно по `valuation_type`.

## Monte Carlo параметры

Для вкладки **Монте-Карло симуляция** дополнительно используются:

- `samples_count` — сколько simulation samples обрабатывается;
- `samples_from` — смещение начального sample;
- `parallel_processes_count` — число parallel processes;
- `format` — формат выходных данных.

`samples_count` влияет на устойчивость распределения и стоимость расчета. Чем больше samples, тем надежнее хвостовые метрики, но тем тяжелее запуск.

`samples_from` обычно нужен для распараллеливания или частичной обработки одного simulation source.

## Debug параметры

Debug fields используются для диагностики расчета:

- `debug_mode`;
- `debug_pricing_dates`;
- `debug_valuations`, если поле доступно в payload.

Debug output может быть тяжелым по объему. Его не стоит включать в регулярных production-запусках без необходимости.

## Как форма строится сейчас

Текущая форма уже частично metadata-driven:

1. Frontend импортирует JSON Schema для `RunDeterministicValuationCommand` и `RunMonteCarloValuationCommand`.
2. Эти JSON Schema генерируются из backend Pydantic models.
3. Форма рендерится через RJSF.
4. Дополнительные frontend overrides подставляют dictionary widgets для сценариев, контрактов, markets, products, countries и supply paths.
5. Layout использует metadata вида `ui:group`, `ui:property_priority`, `ui:full_width`, `dictionary_name`.

То есть источник истины для shape формы — Pydantic model и JSON Schema, а frontend добавляет runtime dictionaries и UI-specific behavior.

## Возможность использовать метаинформацию моделей

Есть три потенциальных источника metadata.

| Источник | Что можно использовать | Оценка |
|---|---|---|
| Pydantic models | `Field`, `description`, `json_schema_extra`, docstrings, constraints | Лучший source of truth на backend |
| JSON Schema | `title`, `description`, `default`, `required`, `dictionary_name`, `ui:*` | Лучший источник для frontend runtime |
| Generated TypeScript client | request/response types и comments из OpenAPI | Полезен для type safety, но слабее для rich UI metadata |

## Рекомендация

Для help и подсказок формы эффективнее использовать JSON Schema, сгенерированную из Pydantic, а не generated TypeScript client.

Причины:

- JSON Schema уже импортируется на экран и доступна в runtime;
- JSON Schema сохраняет `title`, `description`, `default`, `required` и custom `ui:*` metadata;
- RJSF уже умеет использовать schema metadata для labels, widgets и validation;
- TypeScript generated client в основном нужен для compile-time типов и API calls, а не для runtime introspection;
- Pydantic остается upstream source of truth, но frontend не должен напрямую парсить Python-код.

## Что можно улучшить дальше

Возможное развитие без смены публичного API:

1. Добавить более полные `description` в Pydantic `Field(...)` для ключевых параметров запуска.
2. Перегенерировать JSON Schema.
3. На frontend показывать `description` как tooltip/help text рядом с полями RJSF.
4. Использовать `dictionary_name` из schema автоматически, без ручного перечисления отдельных fields в `RunForm`.
5. Сформировать отдельный schema-to-help extractor, который может строить справку по форме из JSON Schema.

## Ограничения metadata-driven подхода

- Не вся бизнес-семантика помещается в короткий `description` поля.
- Cross-field правила, например связь `valuation_type`, `observation_date`, `operation_id` и source path, лучше документировать отдельным help-текстом.
- Generated TypeScript types не должны становиться источником истины для бизнес-семантики.
- Custom frontend overrides все равно нужны для dictionaries, удобного layout и пресетов.

## Практический порядок запуска

1. Выберите вкладку: детерминированный расчет или Monte Carlo.
2. При необходимости выберите пресет.
3. Проверьте даты и `observation_date`.
4. Выберите scenarios.
5. Задайте contract filter.
6. Проверьте `valuation_type` и `engine`.
7. Для Monte Carlo проверьте `samples_count` и parallel settings.
8. Настройте reporting output.
9. Не включайте debug и curve overrides без явной необходимости.
10. Нажмите **Запустить расчёт**.

## Связанные страницы

- [Simulation Analysis](help:valuation-simulation-analysis)
- [Scenario Analysis](help:scenario-analysis)
- [Observation Date Comparison](help:observation-comparison)
