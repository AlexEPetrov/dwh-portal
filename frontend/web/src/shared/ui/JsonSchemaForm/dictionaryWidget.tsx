import type { RegistryWidgetsType } from '@rjsf/utils';
import Select from 'antd/es/select';
import { OperationIdSelectWidget } from './operationIdWidget';

type DictionaryOption = { label: string; value: string };

const DictionarySelectWidget = (props: any) => {
  const { value, onChange, options, schema } = props;
  const selectOptions: DictionaryOption[] = options.options || [];
  const multiple = schema?.type === 'array';

  return (
    <Select
      mode={multiple ? 'multiple' : undefined}
      value={value}
      onChange={(next) => onChange(next ?? (multiple ? [] : undefined))}
      options={selectOptions}
      showSearch
      allowClear
      style={{ width: '100%' }}
      optionFilterProp="label"
      loading={options.loading}
    />
  );
};

export const jsonSchemaWidgets: RegistryWidgetsType = {
  dictionarySelect: DictionarySelectWidget,
  operationIdSelect: OperationIdSelectWidget,
};

