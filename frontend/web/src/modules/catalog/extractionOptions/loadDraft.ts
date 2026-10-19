import { getAsset, getAssetLineage } from '@shared/api/generated';
import type { AssetDetailResponse } from '@shared/api/generated';

export type ExtractionSourceDraft = {
  assetId: string;
  name: string;
  description: string;
  extractSourceTypeId: number | null;
  isActive: boolean;
  extractOptions: Record<string, unknown>;
  storageOptions: Record<string, unknown>;
  loadOptions: {
    enabled: boolean;
    handlers: Array<Record<string, unknown>>;
  };
  sourceProvider: string;
  qualifiedName: string;
};

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};

const PATTERN_KEYS = ['attachment_patterns', 'subject_patterns', 'filename_patterns'] as const;

const normalizeExtractOptions = (value: unknown): Record<string, unknown> => {
  const options = asRecord(value);
  const next = { ...options };
  for (const key of PATTERN_KEYS) {
    const raw = next[key];
    if (raw == null) {
      next[key] = [];
      continue;
    }
    if (Array.isArray(raw)) {
      next[key] = raw.map((item) => String(item ?? '')).filter((item) => item.trim().length > 0);
    }
  }
  return next;
};

const handlerFromProcess = (process: AssetDetailResponse): Record<string, unknown> => {
  const attrs = process.attributes || {};
  const handlerType = String(attrs.handler_type || 'Python');
  const base: Record<string, unknown> = {
    handler_type: handlerType,
    module: attrs.module ?? null,
    entry_point: attrs.entry_point ?? null,
  };
  if (handlerType === 'RestApi') {
    return {
      handler_type: 'RestApi',
      connection_id: attrs.connection_id ?? '',
      url_path: attrs.url_path ?? '',
      timeout_ms: typeof attrs.timeout_ms === 'number' ? attrs.timeout_ms : 300000,
      method: attrs.method ?? 'POST',
      payload: attrs.payload ?? null,
      query_string: attrs.query_string ?? null,
      headers: attrs.headers ?? null,
      retry_count: typeof attrs.retry_count === 'number' ? attrs.retry_count : 0,
    };
  }
  if (handlerType === 'PythonV0') {
    return {
      ...base,
      handler_type: 'PythonV0',
      dependent_matviews: Array.isArray(attrs.dependent_matviews)
        ? attrs.dependent_matviews
        : [],
    };
  }
  return {
    ...base,
    handler_type: 'Python',
  };
};

export const loadExtractionSourceDraft = async (
  assetId: string
): Promise<ExtractionSourceDraft> => {
  const [detail, lineage] = await Promise.all([
    getAsset({ assetId }),
    getAssetLineage({ assetId }),
  ]);

  const attrs = detail.attributes || {};
  const extractOptions = normalizeExtractOptions(attrs.extract_options);

  const storageIds = lineage.nodes
    .filter((node) => node.asset_type === 'STORAGE_LOCATION' && !node.unresolved)
    .map((node) => node.id);
  const processIds = lineage.nodes
    .filter((node) => node.asset_type === 'PROCESS' && !node.unresolved)
    .map((node) => node.id);

  const [storageDetails, processDetails] = await Promise.all([
    Promise.all(storageIds.map((id) => getAsset({ assetId: id }))),
    Promise.all(processIds.map((id) => getAsset({ assetId: id }))),
  ]);

  const storageOptions =
    storageDetails.length > 0 ? asRecord(storageDetails[0].attributes) : {};

  const handlers = processDetails
    .filter((item) => item.source_provider === 'extraction_registry' || Boolean(item.attributes?.handler_type))
    .map(handlerFromProcess);

  return {
    assetId: detail.id,
    name: detail.display_name || detail.name,
    description: detail.description || '',
    extractSourceTypeId:
      typeof attrs.extract_source_type_id === 'number'
        ? attrs.extract_source_type_id
        : attrs.extract_source_type_id == null
          ? null
          : Number(attrs.extract_source_type_id),
    isActive: attrs.is_active !== false,
    extractOptions,
    storageOptions,
    loadOptions: {
      enabled: true,
      handlers,
    },
    sourceProvider: detail.source_provider,
    qualifiedName: detail.qualified_name,
  };
};
