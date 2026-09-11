/**
 * Schema normalization utilities for JSON Schema forms.
 *
 * Flattens anyOf/allOf patterns into direct types with _nullable markers,
 * resolves $ref references, and adds explicit "None" options to nullable enums.
 */

import type { UiSchema } from '@rjsf/utils';

// Collect UI/metadata properties from a schema property
const collectUiProps = (prop: any): Record<string, any> => {
    const uiProps: Record<string, any> = {};
    ['title', 'description', 'ui:property_priority', 'ui:group', 'ui:hidden', 'ui:tab'].forEach(k => {
        if (prop[k] !== undefined) uiProps[k] = prop[k];
    });
    return uiProps;
};

// Resolve a $ref against $defs
const resolveRef = (ref: string, defs: any): any => {
    const refPath = ref.replace('#/$defs/', '');
    return defs?.[refPath];
};

// Add null option to nullable enum
const withNullOption = (enumValues: any[], enumNames?: string[]): { enum: any[]; enumNames: string[] } => {
    const names = enumNames || enumValues.map((v: any) => String(v));
    return {
        enum: [...enumValues, null],
        enumNames: [...names, '—'],
    };
};

// Normalize a single property: flatten anyOf/allOf into direct types with _nullable marker
const normalizeProperty = (prop: any, defs: any): any => {
    // Handle dictionary fields - check if nullable and flatten anyOf
    if (prop.dictionary_name) {
        const uiProps = collectUiProps(prop);

        // Check if it's nullable (anyOf with null)
        if (prop.anyOf) {
            const hasNull = prop.anyOf.some((item: any) => item.type === 'null');
            const nonNullItems = prop.anyOf.filter((item: any) => item.type !== 'null');

            if (hasNull && nonNullItems.length === 1 && nonNullItems[0].type === 'string') {
                // Flatten anyOf: [string, null] to string with _nullable marker
                const result: any = {
                    type: 'string',
                    dictionary_name: prop.dictionary_name,
                    ...uiProps,
                    _nullable: true,
                };
                if (prop.default !== undefined) {
                    result.default = prop.default;
                }
                if (prop.description) {
                    result.description = prop.description;
                }
                return result;
            }
        }
        return prop;
    }

    const uiProps = collectUiProps(prop);

    // Handle allOf: [{$ref}] - resolve non-nullable enum references (e.g. contract_type, pricing_mode)
    if (prop.allOf && !prop.anyOf) {
        const refItem = prop.allOf.find((item: any) => item.$ref);
        if (refItem) {
            const resolved = resolveRef(refItem.$ref, defs);
            if (resolved) {
                return {
                    ...resolved,
                    ...uiProps,
                    default: prop.default !== undefined ? prop.default : resolved.default,
                };
            }
        }
        return prop;
    }

    // Handle anyOf: [X, null] patterns
    if (!prop.anyOf) return prop;

    const hasNull = prop.anyOf.some((item: any) => item.type === 'null');
    if (!hasNull) return prop;

    const nonNullItems = prop.anyOf.filter((item: any) => item.type !== 'null');
    if (nonNullItems.length !== 1) return prop;

    const nonNullItem = nonNullItems[0];

    // Handle $ref — resolve against $defs
    if (nonNullItem.$ref) {
        const resolved = resolveRef(nonNullItem.$ref, defs);
        if (resolved) {
            // If resolved is an enum, add null option
            if (resolved.enum) {
                const nullEnum = withNullOption(resolved.enum, resolved.enumNames);
                return {
                    type: resolved.type,
                    enum: nullEnum.enum,
                    enumNames: nullEnum.enumNames,
                    ...(resolved.description && { description: resolved.description }),
                    ...uiProps,
                    default: prop.default !== undefined ? prop.default : resolved.default,
                    _nullable: true,
                };
            }
            return {
                ...resolved,
                ...uiProps,
                default: prop.default !== undefined ? prop.default : resolved.default,
                _nullable: true,
            };
        }
        return prop;
    }

    // Handle simple types (string, integer, number, etc.)
    if (nonNullItem.type) {
        const result: any = {
            type: nonNullItem.type,
            ...(nonNullItem.format && { format: nonNullItem.format }),
            default: prop.default !== undefined ? prop.default : undefined,
            ...uiProps,
            _nullable: true,
        };

        // For inline enums, add null option
        if (nonNullItem.enum) {
            const nullEnum = withNullOption(nonNullItem.enum, nonNullItem.enumNames);
            result.enum = nullEnum.enum;
            result.enumNames = nullEnum.enumNames;
        }

        return result;
    }

    return prop;
};

/**
 * Recursively normalize a JSON schema:
 * - Flatten anyOf: [X, null] into X with _nullable marker
 * - Resolve allOf: [{$ref}] enum references
 * - Add explicit "None" option to nullable enums
 * - Remove fields with defaults from required array
 */
export const normalizeSchema = (schema: any, rootDefs?: any): any => {
    const result = { ...schema };
    const defs = result.$defs || rootDefs;

    // Recursively normalize $defs (nested model definitions)
    if (result.$defs) {
        const normalizedDefs: Record<string, any> = {};
        Object.entries(result.$defs).forEach(([defName, defSchema]: [string, any]) => {
            if (defSchema && typeof defSchema === 'object' && defSchema.properties) {
                normalizedDefs[defName] = normalizeSchema(defSchema, result.$defs);
            } else {
                normalizedDefs[defName] = defSchema;
            }
        });
        result.$defs = normalizedDefs;
    }

    // Normalize properties
    if (result.properties) {
        const normalizedProps: Record<string, any> = {};
        Object.entries(result.properties).forEach(([key, prop]: [string, any]) => {
            normalizedProps[key] = normalizeProperty(prop, defs);
        });
        result.properties = normalizedProps;

        // Remove fields with default values from required array
        if (result.required && Array.isArray(result.required)) {
            result.required = result.required.filter((fieldName: string) => {
                const prop = normalizedProps[fieldName];
                // Keep in required only if no default value is defined
                return prop && prop.default === undefined;
            });
        }
    }

    return result;
};

/**
 * Generate UI schema from a normalized JSON schema.
 * Maps field types to appropriate widgets with nullable support.
 */
export const generateUiSchema = (schema: any, customFields: Record<string, any> = {}): UiSchema => {
    const uiSchema: UiSchema = {};

    Object.entries(schema.properties || {}).forEach(([key, value]: [string, any]) => {
        // 1. Справочник (dictionary_name) - кастомный виджет
        if (value.dictionary_name) {
            uiSchema[key] = {
                'ui:widget': 'customDictionarySelect',
                'ui:options': {
                    dictionaryName: value.dictionary_name,
                    ...customFields[key],
                },
            };
        }
        // 2. Enum (nullable or not) - select with allowClear for nullable
        else if (value.enum && value.enum.length > 0) {
            uiSchema[key] = {
                'ui:widget': 'select',
                ...(value._nullable && { 'ui:options': { allowClear: true } }),
            };
        }
        // 3. Boolean - checkbox
        else if (value.type === 'boolean') {
            uiSchema[key] = { 'ui:widget': 'checkbox' };
        }
        // 4. Nullable string - text with allowClear
        else if (value.type === 'string' && value._nullable) {
            uiSchema[key] = {
                'ui:widget': 'text',
                'ui:options': { allowClear: true },
            };
        }
        // 5. Nullable number/integer - number with allowClear
        else if ((value.type === 'number' || value.type === 'integer') && value._nullable) {
            uiSchema[key] = {
                'ui:widget': 'updown',
                'ui:options': { allowClear: true },
            };
        }
        // 6. Fallback for anyOf (shouldn't happen after normalization, but just in case)
        else if (value.anyOf) {
            const hasString = value.anyOf.some((item: any) => item.type === 'string');
            const hasNull = value.anyOf.some((item: any) => item.type === 'null');
            if (hasString && hasNull) {
                uiSchema[key] = { 'ui:widget': 'text' };
            }
        }
        // 7. Обычные поля - ничего не задаем (будет text по умолчанию)
    });

    return uiSchema;
};
