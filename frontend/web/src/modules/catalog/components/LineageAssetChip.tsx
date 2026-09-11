import { AimOutlined, ExportOutlined } from '@ant-design/icons';
import { Tag, Tooltip, Typography } from 'antd';
import type { CSSProperties, KeyboardEvent, MouseEvent, MouseEventHandler, ReactNode } from 'react';
import { TYPE_ACCENT, TYPE_COLOR, TYPE_WASH } from './lineageFlow';

type Props = {
  assetType: string;
  title: string;
  unresolved?: boolean;
  /** PROCESS as transition actor — same dashed treatment in list and graph. */
  actor?: boolean;
  /** Currently focused lineage root. */
  selected?: boolean;
  interactive?: boolean;
  /** Open object card (body click / export icon). */
  onOpenObject?: MouseEventHandler<HTMLElement>;
  /** Stay on Lineage and select this asset as the graph root. */
  onSelectInLineage?: MouseEventHandler<HTMLElement>;
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
};

const LineageAssetChip = ({
  assetType,
  title,
  unresolved = false,
  actor = false,
  selected = false,
  interactive = false,
  onOpenObject,
  onSelectInLineage,
  className = '',
  style,
  children,
}: Props) => {
  const accent = unresolved ? '#ff4d4f' : TYPE_ACCENT[assetType] || '#8c8c8c';
  const isProcess = actor || assetType === 'PROCESS';
  const wash = unresolved ? '#fff1f0' : isProcess ? TYPE_WASH.PROCESS || '#ffffff' : '#ffffff';
  const classes = [
    'lineage-asset-chip',
    isProcess ? 'is-process' : '',
    unresolved ? 'is-unresolved' : '',
    interactive ? 'is-interactive' : '',
    selected ? 'is-selected' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const stop = (event: MouseEvent | KeyboardEvent) => {
    event.stopPropagation();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!interactive || !onOpenObject) {
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onOpenObject(event as unknown as Parameters<MouseEventHandler<HTMLElement>>[0]);
    }
  };

  return (
    <div
      className={classes}
      onClick={interactive ? onOpenObject : undefined}
      style={
        {
          '--lineage-accent': accent,
          '--lineage-wash': wash,
          ...style,
        } as CSSProperties
      }
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      onKeyDown={interactive ? onKeyDown : undefined}
    >
      <div className="lineage-asset-chip__actions">
        {onSelectInLineage && !unresolved ? (
          <Tooltip title="Выбрать в Lineage">
            <button
              type="button"
              className="lineage-asset-chip__action"
              aria-label="Выбрать в Lineage"
              onClick={(event) => {
                stop(event);
                onSelectInLineage(event);
              }}
            >
              <AimOutlined />
            </button>
          </Tooltip>
        ) : null}
        {onOpenObject && !unresolved ? (
          <Tooltip title="Открыть карточку">
            <button
              type="button"
              className="lineage-asset-chip__action"
              aria-label="Открыть карточку"
              onClick={(event) => {
                stop(event);
                onOpenObject(event);
              }}
            >
              <ExportOutlined />
            </button>
          </Tooltip>
        ) : null}
      </div>
      {selected ? <span className="lineage-asset-chip__current">текущий</span> : null}
      <Tag
        className="lineage-asset-chip__tag"
        color={unresolved ? 'red' : TYPE_COLOR[assetType]}
      >
        {actor ? 'PROCESS · actor' : assetType}
      </Tag>
      <Typography.Text className="lineage-asset-chip__title" ellipsis>
        {title}
      </Typography.Text>
      {unresolved ? (
        <Typography.Text type="danger" style={{ fontSize: 12 }}>
          unresolved
        </Typography.Text>
      ) : null}
      {children}
    </div>
  );
};

export default LineageAssetChip;
