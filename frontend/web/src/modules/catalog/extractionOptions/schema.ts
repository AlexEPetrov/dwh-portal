import rawBundle from '@common/contracts/jsonschema/extraction_options.json';

export type ExtractionOptionsBundle = typeof rawBundle;

export const extractionOptionsBundle = rawBundle as ExtractionOptionsBundle;

export type OptionsSchemaKey =
  | 'ExtractEmailOptions'
  | 'ExtractFolderSourceOptions'
  | 'ExtractStorageOptions'
  | 'ExtractLoadOptions';

/** Convert draft-2020 `type: ["string","null"]` shapes into RJSF-friendly optional types. */
export const normalizeSchemaForRjsf = (node: unknown): unknown => {
  if (Array.isArray(node)) {
    return node.map(normalizeSchemaForRjsf);
  }
  if (!node || typeof node !== 'object') {
    return node;
  }

  const source = node as Record<string, unknown>;
  const cloned: Record<string, unknown> = { ...source };

  if (Array.isArray(cloned.type)) {
    const types = cloned.type.filter((item): item is string => typeof item === 'string');
    const nonNull = types.filter((item) => item !== 'null');
    if (types.includes('null') && nonNull.length === 1) {
      cloned.type = nonNull[0];
    } else if (nonNull.length === 1) {
      cloned.type = nonNull[0];
    }
  }

  Object.keys(cloned).forEach((key) => {
    if (key === '$ref') {
      return;
    }
    cloned[key] = normalizeSchemaForRjsf(cloned[key]);
  });

  return cloned;
};

export const getOptionsSchema = (key: OptionsSchemaKey): Record<string, unknown> => {
  const defs = extractionOptionsBundle.$defs as Record<string, unknown>;
  const selected = defs[key];
  if (!selected || typeof selected !== 'object') {
    throw new Error(`Missing schema $defs.${key}`);
  }
  // Editor forms must not render unknown jsonb keys as broken additional fields.
  return normalizeSchemaForRjsf({
    ...(selected as Record<string, unknown>),
    additionalProperties: false,
    $defs: defs,
  }) as Record<string, unknown>;
};

export const pickSchemaFormData = (
  schema: Record<string, unknown>,
  data: Record<string, unknown>
): Record<string, unknown> => {
  const properties = (schema.properties || {}) as Record<string, unknown>;
  const picked: Record<string, unknown> = {};
  Object.keys(properties).forEach((name) => {
    if (Object.prototype.hasOwnProperty.call(data, name)) {
      picked[name] = data[name];
      return;
    }
    const property = properties[name] as { type?: string } | undefined;
    if (property?.type === 'array') {
      picked[name] = [];
    }
  });
  return picked;
};

export const mergeSchemaFormData = (
  schema: Record<string, unknown>,
  previous: Record<string, unknown>,
  next: Record<string, unknown>
): Record<string, unknown> => {
  const properties = (schema.properties || {}) as Record<string, unknown>;
  const merged = { ...previous };
  Object.keys(properties).forEach((name) => {
    if (Object.prototype.hasOwnProperty.call(next, name)) {
      merged[name] = next[name];
    }
  });
  return merged;
};

export const extractSchemaKeyForTypeId = (
  extractSourceTypeId: number | null | undefined
): 'ExtractEmailOptions' | 'ExtractFolderSourceOptions' => {
  if (extractSourceTypeId === 1 || extractSourceTypeId == null) {
    return 'ExtractEmailOptions';
  }
  return 'ExtractFolderSourceOptions';
};
