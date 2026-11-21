import { updateCatalogFilters } from './navigation';

export const CATALOG_ASSET_TYPES = [
    { key: 'DATA_SOURCE', label: 'Источники данных' },
    { key: 'EXTRACTION_SOURCE', label: 'Источники извлечения' },
    { key: 'PROCESS', label: 'Процессы' },
    { key: 'STORAGE_LOCATION', label: 'Места хранения' },
    { key: 'DATABASE', label: 'Базы данных' },
    { key: 'SCHEMA', label: 'Схемы' },
    { key: 'TABLE', label: 'Таблицы' },
    { key: 'VIEW', label: 'Представления' },
    { key: 'MATERIALIZED_VIEW', label: 'Материализованные представления' },
] as const;

// Hide the database tile only on the overview; databases remain searchable catalog objects.
export const OVERVIEW_ASSET_TYPES = CATALOG_ASSET_TYPES.filter(({ key }) => key !== 'DATABASE');

export const catalogTypeUrl = (type: string): string =>
    `/objects?${updateCatalogFilters(new URLSearchParams(), { type, status: 'active' })}`;
