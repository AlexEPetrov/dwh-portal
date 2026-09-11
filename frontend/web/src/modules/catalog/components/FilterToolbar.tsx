import { Button, Space } from 'antd';
import type { ReactNode } from 'react';
import './catalogFilters.css';

export type FilterChipOption = {
  key: string;
  label: string;
};

type ChipGroupProps = {
  options: readonly FilterChipOption[];
  selected: string[];
  onToggle: (key: string) => void;
};

/** Compact Ant button group (shared Objects / Changes toolbar). */
export const FilterChipGroup = ({ options, selected, onToggle }: ChipGroupProps) => (
  <Space.Compact size="small">
    {options.map((option) => {
      const active = selected.includes(option.key);
      return (
        <Button
          key={option.key}
          type={active ? 'primary' : 'default'}
          onClick={() => onToggle(option.key)}
        >
          {option.label}
        </Button>
      );
    })}
  </Space.Compact>
);

type FilterToolbarProps = {
  children: ReactNode;
};

export const FilterToolbar = ({ children }: FilterToolbarProps) => (
  <div className="catalog-filter-bar">{children}</div>
);

export const FilterSep = () => <div className="catalog-filter-sep" aria-hidden />;

type ClearProps = {
  visible: boolean;
  onClick: () => void;
};

export const FilterClear = ({ visible, onClick }: ClearProps) =>
  visible ? (
    <Button size="small" type="link" onClick={onClick} style={{ paddingInline: 4 }}>
      Сбросить
    </Button>
  ) : null;
