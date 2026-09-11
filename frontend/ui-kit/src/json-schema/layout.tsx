import type { FieldTemplateProps, ObjectFieldTemplateProps } from '@rjsf/utils';
import { Alert, Col, Row } from 'antd';

export type UiGroupMeta = {
  name: string;
  title?: string;
  priority?: number;
};

const toPositiveInt = (v: any, fallback: number) => {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? Math.round(n) : fallback;
};

const getGridColumns = (rootSchema: any) => {
  const base = toPositiveInt(rootSchema?.['ui:grid_columns'], 0);
  if (base > 0) {
    return { xs: 1, sm: base, md: base, lg: base, xl: base };
  }

  return {
    xs: toPositiveInt(rootSchema?.['ui:grid_columns_xs'], 1),
    sm: toPositiveInt(rootSchema?.['ui:grid_columns_sm'], 2),
    md: toPositiveInt(rootSchema?.['ui:grid_columns_md'], 2),
    lg: toPositiveInt(rootSchema?.['ui:grid_columns_lg'], 3),
    xl: toPositiveInt(rootSchema?.['ui:grid_columns_xl'], 4),
  };
};

const getColSpan = (rootSchema: any, fieldName: string, currentProps?: Record<string, any>) => {
  // Resolve field metadata from the current object's schema first (handles nested
  // objects where properties live inside their own schema, not at the root),
  // then fall back to rootSchema for backward compatibility.
  const fieldMeta = currentProps?.[fieldName] || rootSchema?.properties?.[fieldName] || {};
  const grid = getGridColumns(rootSchema);

  const byBp = fieldMeta['ui:col_span_by_breakpoint'] || {};
  const baseSpan = toPositiveInt(fieldMeta['ui:col_span'], 1);

  const build = (bp: 'xs' | 'sm' | 'md' | 'lg' | 'xl') => {
    const cols = toPositiveInt((grid as any)[bp], 1);
    const desired = toPositiveInt(byBp[bp], baseSpan);
    const used = Math.max(1, Math.min(desired, cols));
    return Math.round((24 * used) / cols);
  };

  return {
    xs: build('xs'),
    sm: build('sm'),
    md: build('md'),
    lg: build('lg'),
    xl: build('xl'),
  };
};

export const normalizeOptionalSchema = (node: any): any => {
  if (Array.isArray(node)) return node.map(normalizeOptionalSchema);
  if (!node || typeof node !== 'object') return node;

  const cloned: any = { ...node };
  if (Array.isArray(cloned.anyOf)) {
    const nonNull = cloned.anyOf.filter((x: any) => x?.type !== 'null');
    if (nonNull.length === 1) {
      const merged = normalizeOptionalSchema(nonNull[0]);
      delete cloned.anyOf;
      return { ...cloned, ...merged };
    }
  }

  Object.keys(cloned).forEach((key) => {
    cloned[key] = normalizeOptionalSchema(cloned[key]);
  });
  return cloned;
};

export const DefaultFieldTemplate = ({ id, label, children, required, rawErrors, hidden }: FieldTemplateProps) => {
  if (hidden) return null;
  return (
    <div style={{ width: '100%' }}>
      {label && (
        <label htmlFor={id} style={{ display: 'block', marginBottom: 4, fontWeight: 500 }}>
          {label}{required ? ' *' : ''}
        </label>
      )}
      {children}
      {rawErrors && rawErrors.length > 0 ? <Alert message={rawErrors[0]} type="error" showIcon style={{ marginTop: 4 }} /> : null}
    </div>
  );
};

export const GroupedObjectFieldTemplate = ({ properties, registry, schema }: ObjectFieldTemplateProps) => {
  const rootSchema = (registry as any)?.formContext?.rootSchema || {};
  // Current object's own schema properties — contains ui:* metadata for nested fields.
  // For nested objects, pydantic json_schema_extra is emitted into $defs.<TypeName>.properties,
  // which RJSF resolves into schema.properties. Root-level fields live in rootSchema.properties.
  const currentProps = ((schema as any)?.properties || {}) as Record<string, any>;
  const propMap = new Map(properties.map((p: any) => [p.name, p.content]));
  const names: string[] = properties.map((p: any) => p.name);

  // Resolve field metadata: current object's schema first (nested objects),
  // then rootSchema (top-level form fields). This ensures ui:group / ui:full_width /
  // ui:col_span work at every nesting level.
  const lookupMeta = (name: string) => {
    return currentProps[name] || rootSchema?.properties?.[name] || {};
  };

  const groups = new Map<string, { meta: UiGroupMeta; fields: string[] }>();
  const withoutGroup: string[] = [];

  names.forEach((name) => {
    const meta = lookupMeta(name);
    const group = meta['ui:group'] as UiGroupMeta | undefined;
    if (!group?.name) {
      withoutGroup.push(name);
      return;
    }
    if (!groups.has(group.name)) {
      groups.set(group.name, { meta: group, fields: [] });
    }
    groups.get(group.name)!.fields.push(name);
  });

  const sortByPriority = (fieldNames: string[]) =>
    [...fieldNames].sort((a, b) => {
      const pa = lookupMeta(a)?.['ui:property_priority'] ?? 999;
      const pb = lookupMeta(b)?.['ui:property_priority'] ?? 999;
      return pa - pb;
    });

  const renderFields = (fieldNames: string[]) => {
    const full = sortByPriority(fieldNames).filter((f) => !!lookupMeta(f)?.['ui:full_width']);
    const regular = sortByPriority(fieldNames).filter((f) => !lookupMeta(f)?.['ui:full_width']);

    return (
      <>
        {full.map((f) => (
          <div key={f} style={{ marginBottom: 12 }}>{propMap.get(f)}</div>
        ))}
        {regular.length > 0 && (
          <Row gutter={[16, 12]}>
            {regular.map((f) => (
              <Col key={f} {...getColSpan(rootSchema, f, currentProps)}>
                {propMap.get(f)}
              </Col>
            ))}
          </Row>
        )}
      </>
    );
  };

  const sortedGroups = [...groups.values()].sort(
    (a, b) => (a.meta.priority ?? 999) - (b.meta.priority ?? 999)
  );

  return (
    <div>
      {renderFields(withoutGroup)}
      {sortedGroups.map((g) => (
        <div key={g.meta.name} style={{ marginTop: 20 }}>
          <div style={{ fontWeight: 600, marginBottom: 10 }}>{g.meta.title || g.meta.name}</div>
          {renderFields(g.fields)}
        </div>
      ))}
    </div>
  );
};
