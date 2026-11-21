// src/mocks/data/contracts.ts
export const mockContracts: Array<Record<string, unknown>> = [
  {
    id: '1',
    name: 'B export (longterm)',
    slug: 'b-export-lt',
    counterparty: 'BP Export LLC',
    volume_uom: 'MWh',
    pricing_uom: 'EUR/MWh',
    is_active: true,
    balance_position: 'revenue_trading',
  },
  {
    id: '2',
    name: 'Shell Energy Europe (spot)',
    slug: 'shell-energy-spot',
    counterparty: 'Shell Energy Europe Ltd',
    volume_uom: 'MWh',
    pricing_uom: 'EUR/MWh',
    is_active: true,
    balance_position: 'revenue_trading',
  },
  {
    id: '3',
    name: 'Uniper Global Commodities',
    slug: 'uniper-gc',
    counterparty: 'Uniper Global Commodities SE',
    volume_uom: 'MWh',
    pricing_uom: 'USD/MMBtu',
    is_active: false,
    balance_position: 'tax',
  },
];
