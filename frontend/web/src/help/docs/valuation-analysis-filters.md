# Верхние фильтры анализа

Этот документ описывает общий верхний блок фильтров, который используется на страницах **Simulation Analysis**, **Scenario Analysis** и **Observation Date Comparison**.

## Общая идея

Верхние фильтры отвечают на четыре вопроса:

1. Откуда брать данные: напрямую из simulation rows или из сохраненного balance tree.
2. Какой simulation run использовать: observation date, valuation type и scenario.
3. Какой период анализировать: valuation-period или payment-period.
4. Какую часть портфеля выбрать: markets, products, GL accounts и другие scope filters.

После изменения фильтров нужно нажать кнопку загрузки или запуска анализа. Переключение вкладок внутри одного экрана не всегда означает новый backend-запрос, если данные для выбранных параметров уже загружены.

## Источник: по симуляциям или по балансу

| Источник | Что означает | Когда использовать |
|---|---|---|
| По симуляциям | Прямой анализ строк Monte Carlo simulation results | Нужно посмотреть распределение по market/product/GL/period без balance tree |
| По балансу | Hybrid-анализ через выбранное GL Balance tree | Нужно анализировать агрегированную структуру баланса и его узлы |

## По симуляциям

В режиме **По симуляциям** backend читает simulation results и применяет выбранные фильтры напрямую к строкам факта симуляции.

Обычно доступны:

- `Observation date` — дата partition/run, с которой читаются simulation results;
- `Scenario` — опциональный scenario partition;
- `Period from` и `Period to` — границы периода;
- `Mode` — способ интерпретации периода;
- `Currency` или `target` — выбранная величина;
- `Markets`, `Products`, `GL accounts` и другие scope filters.

Этот режим удобен для прямого ответа: “какое распределение у выбранного среза simulation rows?”.

## По балансу

В режиме **По балансу** пользователь выбирает GL Balance tree. Backend строит hybrid view: объединяет simulation component и сохраненную static component дерева.

Особенности:

- выбранный balance tree обязателен;
- обычные scope filters могут быть скрыты или не применяться так же, как в filter mode;
- периодная семантика для balance mode payments-based;
- результат отражает структуру balance tree, а не простой срез raw simulation rows.

Этот режим удобен, когда бизнес-вопрос задан в терминах балансовой структуры: “как ведет себя выбранное дерево или его узлы?”.

## Observation date

`Observation date` выбирает расчетный simulation run или partition наблюдения.

Бизнес-смысл: это дата, на которую доступны входные рыночные данные, сценарии и результаты расчета. Смена `Observation date` может существенно менять результат, потому что меняется исходное состояние рынка и набор доступных simulation results.

## Scenario

`Scenario` ограничивает данные конкретным scenario partition, если он выбран. Если scenario не выбран, данные могут агрегироваться по всем доступным scenario partitions согласно backend semantics конкретного endpoint.

Используйте scenario filter, если нужно сравнить или изолировать конкретную бизнес-гипотезу внутри simulation results.

## Period from / Period to

Период задает границы анализа. Интерпретация зависит от `Mode`.

Границы обычно трактуются на уровне месяца и включают начальный и конечный месяц.

## Mode: Valuations, Payments, Prices

| Mode | Как выбирается период | Что означает |
|---|---|---|
| Valuations | По valuation-period | Анализ результата по месяцу оценки/поставки в valuation layer |
| Payments | По payment-period | Анализ результата по месяцу платежа или cash-flow timing |
| Prices | По valuation-period, но target считается как цена | Анализ derived price: `sum(value) / sum(volume)` |

### Valuations

Используйте **Valuations**, если вопрос относится к периоду оценки, поставки или valuation month.

### Payments

Используйте **Payments**, если вопрос относится к денежному потоку и календарю платежей.

Для liquidity analysis чаще всего важен именно payment timing, потому что кассовый разрыв зависит от того, когда деньги фактически приходят или уходят.

### Prices

**Prices** — это derived view. Пользователь выбирает валюту, а backend считает цену как отношение стоимости к объему:

```text
price = sum(value_rub_or_usd) / sum(volume)
```

Этот режим нужен, когда важна не абсолютная выручка или денежный поток, а средняя цена.

## Currency / target

Для денежных режимов обычно выбирается:

- `RUB` — значения в рублях;
- `USD` — значения в долларах.

Для `Prices` выбор валюты определяет валюту цены.

Важно: target задает то, что будет агрегироваться, отображаться в статистике, распределении и raw values.

## Scope filters

Scope filters ограничивают область данных:

- markets;
- products;
- GL accounts;
- contract attributes;
- другие доступные business dimensions.

Чем уже фильтр, тем меньше sample rows попадает в выборку. Если после фильтрации выборка пустая, статистика и графики будут пустыми.

## Типовые сценарии использования

| Задача | Рекомендуемый источник | Рекомендуемый mode |
|---|---|---|
| Посмотреть распределение P&L по продукту | По симуляциям | Valuations |
| Посмотреть cash-flow timing и liquidity risk | По симуляциям или по балансу | Payments |
| Проанализировать баланс по сохраненному дереву | По балансу | Payments-based view |
| Посмотреть среднюю цену по сценариям | По симуляциям | Prices |
| Запустить factor shocks для выбранного portfolio slice | По симуляциям | Valuations или Payments |
| Запустить factor shocks для balance tree | По балансу | Payments-based view |

## Частые ошибки интерпретации

- Не сравнивайте результаты `Valuations` и `Payments` как одинаковую бизнес-величину: они отвечают на разные вопросы периода.
- Не интерпретируйте `Prices` как сумму денег: это derived price.
- Не смешивайте raw simulation rows и balance-derived results: balance mode строит производное представление.
- Не считайте пустой график frontend-ошибкой до проверки фильтров: часто это означает, что выбранный срез не содержит данных.
- Не меняйте `Observation date` без понимания: это может означать другой набор simulation results.

## Связанные страницы

- [Simulation Analysis](help:valuation-simulation-analysis)
- [Scenario Analysis](help:scenario-analysis)
- [Observation Date Comparison](help:observation-comparison)
