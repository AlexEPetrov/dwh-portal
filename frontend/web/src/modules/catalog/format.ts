import type { FreshnessItem } from '@shared/api/generated';
import dayjs from 'dayjs';

export function formatBytes(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '—';
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  let amount = value;
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${amount.toLocaleString('ru-RU', { maximumFractionDigits: amount >= 10 ? 1 : 2 })} ${units[unit]}`;
}

export function formatRows(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '—';
  }
  if (Math.abs(value) >= 1_000_000_000) {
    return `~${(value / 1_000_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} B`;
  }
  if (Math.abs(value) >= 1_000_000) {
    return `~${(value / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 0 })} M`;
  }
  return `~${value.toLocaleString('ru-RU')}`;
}

export function formatDateTime(value?: string | null): string {
  if (!value) {
    return '—';
  }
  return dayjs(value).format('DD MMM YYYY HH:mm');
}

export function freshnessLabel(items?: FreshnessItem[] | null): string {
  if (!items?.length) {
    return 'Свежесть снимков неизвестна';
  }
  return items
    .map((item) => `${item.collector_name}: ${item.status} ${formatDateTime(item.finished_at)}`)
    .join(' · ');
}

export function changeGlyph(changeType: string): string {
  if (changeType === 'ADDED') return '+';
  if (changeType === 'REMOVED') return '-';
  return '~';
}
