import {
    getContractsListApiManagementContractsGet,
    getCountriesListApiManagementCountriesGet,
    getGlAccountsListApiManagementGlAccountsGet,
    getIndexesListApiManagementIndexesGet,
    getLegalEntitiesListApiManagementDeliveryMarketsGet,
    getLegalEntitiesListApiManagementLegalEntitiesGet,
    getLegalEntitiesListApiManagementProductsGet,
    getScenariosListApiManagementScenariosGet,
    getSupplyPathsListApiManagementSupplyPathsGet,
    type CountryModel,
    type DeliveryMarketModel,
    type GlAccountModel,
    type LegalEntityModel,
    type ObjectInfoModel,
    type ProductModel,
    type SupplyPathModel
} from './generated';

export type DictionaryOption = { label: string; value: string };

const toOption = (item: { name?: string; slug?: string | null }): DictionaryOption | null => {
    const value = item.slug || item.name || '';
    if (!value) return null;
    return { label: item.name || item.slug || value, value };
};

const mapOptions = <T extends { name?: string; slug?: string | null }>(items: T[]): DictionaryOption[] =>
    items.map(toOption).filter((x): x is DictionaryOption => x !== null);

// Module-level cache for dictionary data
const dictionaryCache = new Map<string, DictionaryOption[]>();

export const loadDictionaryByName = async (dictionaryName: string): Promise<DictionaryOption[]> => {
    // Check cache first
    if (dictionaryCache.has(dictionaryName)) {
        return dictionaryCache.get(dictionaryName)!;
    }

    // Load from API
    const options = await loadDictionaryFromApi(dictionaryName);

    // Cache result
    dictionaryCache.set(dictionaryName, options);

    return options;
};

// Optional: Add cache invalidation
export const clearDictionaryCache = (dictionaryName?: string) => {
    if (dictionaryName) {
        dictionaryCache.delete(dictionaryName);
    } else {
        dictionaryCache.clear();
    }
};

const loadDictionaryFromApi = async (dictionaryName: string): Promise<DictionaryOption[]> => {
    switch (dictionaryName) {
        case 'legal_entities': {
            const data = await getLegalEntitiesListApiManagementLegalEntitiesGet();
            return mapOptions(data as LegalEntityModel[]);
        }
        case 'delivery_markets': {
            const data = await getLegalEntitiesListApiManagementDeliveryMarketsGet();
            return mapOptions(data as DeliveryMarketModel[]);
        }
        case 'products': {
            const data = await getLegalEntitiesListApiManagementProductsGet();
            return mapOptions(data as ProductModel[]);
        }
        case 'countries': {
            const data = await getCountriesListApiManagementCountriesGet();
            return mapOptions(data as CountryModel[]);
        }
        case 'supply_paths': {
            const data = await getSupplyPathsListApiManagementSupplyPathsGet();
            return mapOptions(data as SupplyPathModel[]);
        }
        case 'scenarios': {
            const data = await getScenariosListApiManagementScenariosGet();
            return mapOptions(data as ObjectInfoModel[]);
        }
        case 'contracts': {
            const xApiKey = localStorage.getItem('x_api_key') || 'dev';
            const data = await getContractsListApiManagementContractsGet({ xApiKey });
            return mapOptions(data as ObjectInfoModel[]);
        }
        case 'counterparties': {
            const data = await getLegalEntitiesListApiManagementLegalEntitiesGet();
            return mapOptions(data as LegalEntityModel[]);
        }
        case 'gl_accounts': {
            const data = await getGlAccountsListApiManagementGlAccountsGet();
            return mapOptions(data as GlAccountModel[]);
        }
        case 'indexes': {
            const data = await getIndexesListApiManagementIndexesGet();
            return mapOptions(data as ObjectInfoModel[]);
        }
        default:
            return [];
    }
};
