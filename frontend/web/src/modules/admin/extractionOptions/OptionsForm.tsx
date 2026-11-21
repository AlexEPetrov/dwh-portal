import Form from '@rjsf/antd';
import type {
  FieldTemplateProps,
  ObjectFieldTemplateProps,
  RJSFSchema,
  UiSchema,
} from '@rjsf/utils';
import validator from '@rjsf/validator-ajv8';
import { Typography } from 'antd';
import { useMemo } from 'react';
import './optionsForm.css';
import RegexPatternListWidget from './RegexPatternListWidget';
import {
  getOptionsSchema,
  mergeSchemaFormData,
  pickSchemaFormData,
  type OptionsSchemaKey,
} from './schema';

type OptionsFormProps = {
  schemaKey: OptionsSchemaKey;
  formData: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
  disabled?: boolean;
};

const FIELD_META: Record<string, { title: string; description?: string }> = {
  attachment_patterns: {
    title: 'Шаблоны вложений',
    description: 'Regex по имени файла вложения',
  },
  subject_patterns: {
    title: 'Шаблоны темы письма',
    description: 'Regex по теме письма',
  },
  filename_patterns: {
    title: 'Шаблоны имён файлов',
    description: 'Regex по имени файла в папке',
  },
  folder_path: { title: 'Папка источника' },
  remove_strings: { title: 'Удалять из имени' },
  filename_template: { title: 'Шаблон имени файла' },
  archive_subfolder_template: { title: 'Подпапка архива' },
  inbox_subfolder_template: { title: 'Подпапка inbox' },
  path: { title: 'Путь хранения' },
  need_to_unpack: { title: 'Распаковывать архив' },
  comment: { title: 'Комментарий' },
  enabled: { title: 'Загрузка включена' },
  handlers: { title: 'Обработчики' },
};

const PATTERN_FIELDS = new Set([
  'attachment_patterns',
  'subject_patterns',
  'filename_patterns',
]);

const StackObjectFieldTemplate = ({ properties }: ObjectFieldTemplateProps) => (
  <div className="extraction-options-stack">
    {properties.map((property) => (
      <div key={property.name} className="extraction-options-stack__item">
        {property.content}
      </div>
    ))}
  </div>
);

const CompactFieldTemplate = ({
  id,
  label,
  children,
  required,
  rawErrors,
  hidden,
  schema,
}: FieldTemplateProps) => {
  if (hidden) return null;
  if (schema?.type === 'object' && !label) {
    return <div className="extraction-options-field extraction-options-field--root">{children}</div>;
  }
  return (
    <div className="extraction-options-field">
      {label ? (
        <label htmlFor={id} className="extraction-options-field__label">
          {label}
          {required ? ' *' : ''}
        </label>
      ) : null}
      {schema?.description ? (
        <Typography.Paragraph type="secondary" className="extraction-options-field__hint">
          {schema.description}
        </Typography.Paragraph>
      ) : null}
      <div className="extraction-options-field__control">{children}</div>
      {rawErrors && rawErrors.length > 0 ? (
        <Typography.Text type="danger" className="extraction-options-field__error">
          {rawErrors[0]}
        </Typography.Text>
      ) : null}
    </div>
  );
};

const buildUiSchema = (schema: RJSFSchema): UiSchema => {
  const properties = (schema.properties || {}) as Record<string, unknown>;
  const ui: UiSchema = {
    'ui:title': ' ',
    'ui:description': ' ',
    'ui:submitButtonOptions': { norender: true },
  };
  Object.keys(properties).forEach((name) => {
    const meta = FIELD_META[name];
    ui[name] = {
      ...(PATTERN_FIELDS.has(name) ? { 'ui:widget': 'RegexPatternList' } : {}),
      ...(meta?.title ? { 'ui:title': meta.title } : {}),
      ...(meta?.description ? { 'ui:description': meta.description } : {}),
    };
  });
  return ui;
};

const localizeSchemaTitles = (schema: RJSFSchema): RJSFSchema => {
  const next = { ...schema, title: undefined, description: undefined } as RJSFSchema;
  const props = { ...(schema.properties || {}) } as Record<string, Record<string, unknown>>;
  Object.keys(props).forEach((name) => {
    const meta = FIELD_META[name];
    props[name] = {
      ...props[name],
      title: meta?.title || props[name].title || name,
      description: meta?.description || props[name].description,
    };
  });
  next.properties = props;
  return next;
};

const OptionsForm = ({ schemaKey, formData, onChange, disabled }: OptionsFormProps) => {
  const schema = useMemo(
    () => localizeSchemaTitles(getOptionsSchema(schemaKey) as RJSFSchema),
    [schemaKey]
  );
  const uiSchema = useMemo(() => buildUiSchema(schema), [schema]);
  const safeFormData = useMemo(
    () => pickSchemaFormData(schema as Record<string, unknown>, formData),
    [schema, formData]
  );

  return (
    <div className="extraction-options-form">
      <Form
        schema={schema}
        uiSchema={uiSchema}
        formData={safeFormData}
        validator={validator}
        disabled={disabled}
        liveValidate={false}
        showErrorList={false}
        omitExtraData
        liveOmit
        templates={{
          FieldTemplate: CompactFieldTemplate,
          ObjectFieldTemplate: StackObjectFieldTemplate,
        }}
        widgets={{
          RegexPatternList: RegexPatternListWidget,
        }}
        onChange={(event) => {
          onChange(
            mergeSchemaFormData(
              schema as Record<string, unknown>,
              formData,
              (event.formData || {}) as Record<string, unknown>
            )
          );
        }}
      >
        <div />
      </Form>
    </div>
  );
};

export default OptionsForm;
