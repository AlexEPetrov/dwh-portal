import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { loadDictionaryByName, type DictionaryOption } from '@shared/api/dictionaries';
import type { ValuationFilterRule } from '@shared/valuation-analysis/sourceMode';
import { Button, DatePicker, Select, Space, Tag } from 'antd';
import dayjs from 'dayjs';
import { useEffect, useState } from 'react';

interface Props {
  value: ValuationFilterRule[];
  onChange: (value: ValuationFilterRule[]) => void;
}

const ValuationFilterRulesEditor = ({ value, onChange }: Props) => {
  const [markets, setMarkets] = useState<DictionaryOption[]>([]);
  const [products, setProducts] = useState<DictionaryOption[]>([]);
  const [supplyPaths, setSupplyPaths] = useState<DictionaryOption[]>([]);
  useEffect(() => {
    void Promise.all([
      loadDictionaryByName('delivery_markets'),
      loadDictionaryByName('products'),
      loadDictionaryByName('supply_paths'),
    ]).then(([nextMarkets, nextProducts, nextSupplyPaths]) => {
      setMarkets(nextMarkets);
      setProducts(nextProducts);
      setSupplyPaths(nextSupplyPaths);
    });
  }, []);
  const update = (index: number, patch: Partial<ValuationFilterRule>) => onChange(value.map((rule, i) => i === index ? { ...rule, ...patch } : rule));
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      {value.map((rule, index) => (
        <Space wrap key={index}>
          <Select value={rule.action} onChange={(action) => update(index, { action })} options={[{ value: 'include', label: 'Include' }, { value: 'exclude', label: 'Exclude' }]} />
          <Select mode="multiple" allowClear placeholder="Markets" value={rule.market} options={markets} onChange={(market) => update(index, { market })} style={{ width: 220 }} />
          <Select mode="multiple" allowClear placeholder="Products" value={rule.product} options={products} onChange={(product) => update(index, { product })} style={{ width: 220 }} />
          <Select mode="multiple" allowClear placeholder="Supply paths" value={rule.supply_path} options={supplyPaths} onChange={(supply_path) => update(index, { supply_path })} style={{ width: 220 }} />
          <DatePicker value={rule.period_from ? dayjs(rule.period_from) : null} onChange={(date) => update(index, { period_from: date?.format('YYYY-MM-DD') })} placeholder="From" />
          <DatePicker value={rule.period_to ? dayjs(rule.period_to) : null} onChange={(date) => update(index, { period_to: date?.format('YYYY-MM-DD') })} placeholder="To" />
          <Button danger icon={<DeleteOutlined />} onClick={() => onChange(value.filter((_, i) => i !== index))} />
        </Space>
      ))}
      <Button icon={<PlusOutlined />} onClick={() => onChange([...value, { action: 'exclude' }])}>Add rule</Button>
      {value.length > 0 && (
        <Tag color="blue">
          Main filters AND rules; include rules OR together, exclude rules remove matching rows
        </Tag>
      )}
    </Space>
  );
};

export default ValuationFilterRulesEditor;
