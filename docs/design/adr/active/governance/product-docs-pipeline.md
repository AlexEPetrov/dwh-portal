# ADR: Пайплайн продуктовой AsciiDoc-документации

## Статус

Принято. 2026-09-09.

## Контекст

После разделения слоёв (OpenSpec / ADR / userguide) не хватало продуктового
нарратива для онбординга и внешней публикации. Userguide остаётся
детерминированной in-app справкой; тащить туда «что за продукт» нельзя.
Нужен выход в static HTML на базе AsciiDoc (Antora и аналоги), без возврата
к Sphinx и без серверного runtime для чтения.

## Решение

Продуктовая документация собирается так:

```text
openspec/specs/** + openspec/capabilities.yaml
docs/product/**                 (компактный authored spine)
docs/product/adr-capability-map.yaml
docs/product/capability-help-map.yaml
        │
        ▼  python3 infra/scripts/product_docs_sync.py --mode sync
docs/generated/product/**       Antora-компонент (коммитится)
docs/generated/product/facts/   JSON facts для будущего enrich
        │
        ▼  Antora / AsciiDoctor (CI или потребитель)
static HTML                     артефакт сборки, в Git не хранится
```

Правила:

1. **`sync`** — детерминированная пересборка без AI; зарегистрирована в
   `rules/policy.yaml` как `PRODUCT-DOCS-SYNC`.
2. **`enrich`** — AI-слой только по явному запросу человека; не смешивается
   с `sync`; не вводит MUST/новые capability; подлежит review перед merge.
3. Файлы в `docs/generated/**` помечены `DO NOT EDIT`; правятся только источники.
4. Во внешний компонент попадают **не все** ADR, а только curated map.
5. Capability-страницы содержат Purpose из спеки, help-ссылки и related ADR —
   без Requirements/Scenarios. Основной продуктовый текст — русский
   (spine + enrich); английский Purpose показывается как исходник OpenSpec.
6. `capabilities.yaml` — **справочник** направлений и features (в том числе
   будущих). Промежуточные узлы с `children:` — домены/направления; листья —
   capability. **Любая** `openspec/specs/<path>/spec.md` SHALL иметь лист с
   тем же path в этом файле: спека вне справочника недопустима, sync падает
   (exit 2). Обратное неверно: лист без спеки — допустимая заготовка.
   Порядок создания: сначала узел в `capabilities.yaml`, потом `spec.md`.
   Product-docs публикует пересечение «лист yaml ∩ spec.md».
7. Enrich-тексты лежат в `docs/generated/product-enrich/**`, пишутся агентом
   только по явному запросу; CLI `--mode enrich` лишь валидирует и пересобирает.

## Последствия

* Появляется `docs/product/` как единственный рукописный продуктовый канон.
* AsciiDoc промежуточный слой хранится в Git; HTML — нет.
* Policy обновляет прежнее утверждение «AsciiDoc не хранить в Git».

## Связанные документы

* `docs/product/BUILD.adoc` — как собирать (локально / CI; Cursor и ZooCode)
* `docs/documentation-policy.md`
* `docs/adr/active/governance/documentation-layers.md`
* `infra/scripts/product_docs_sync.py`
* `infra/scripts/product_docs_build.sh`
