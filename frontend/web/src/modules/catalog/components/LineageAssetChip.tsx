import { AimOutlined, ExperimentOutlined, ExportOutlined } from '@ant-design/icons';
import { Tag, Tooltip, Typography } from 'antd';
import type { CSSProperties, KeyboardEvent, MouseEvent, MouseEventHandler, ReactNode } from 'react';
import { TYPE_ACCENT, TYPE_COLOR } from './lineageFlow';

type Props = {
  assetType: string;
  title: string;
  /** Where the object was parsed from: Airflow DAG path or registry module. */
  hint?: string | null;
  unresolved?: boolean;
  /** PROCESS as transition actor — same dashed treatment in list and graph. */
  actor?: boolean;
  /**
   * When false, omit the type Tag (e.g. roots overview already groups by type).
   * Color accent on the chip border still reflects the type.
   */
  showType?: boolean;
  /** Lineage root from the page route. Shows the «текущий» badge. */
  selected?: boolean;
  /** Clicked asset whose dependencies are shown beside it. */
  focused?: boolean;
  interactive?: boolean;
  /** Open object card (export icon). */
  onOpenObject?: MouseEventHandler<HTMLElement>;
  /** Open immersive Universe for this asset. */
  onOpenUniverse?: MouseEventHandler<HTMLElement>;
  /** Click on the chip body: focus this asset in place. */
  onActivate?: MouseEventHandler<HTMLElement>;
  /** Same as body click; kept for the aim icon. */
  onSelectInLineage?: MouseEventHandler<HTMLElement>;
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
};

const LineageAssetChip = ({
  assetType,
  title,
  hint = null,
  unresolved = false,
  actor = false,
  showType = true,
  selected = false,
  focused = false,
  interactive = false,
  onOpenObject,
  onOpenUniverse,
  onActivate,
  onSelectInLineage,
  className = '',
  style,
  children,
}: Props) => {
  const accent = unresolved ? '#ff4d4f' : TYPE_ACCENT[assetType] || '#8c8c8c';
  const isProcess = actor || assetType === 'PROCESS';
  const classes = [
    'lineage-asset-chip',
    isProcess ? 'is-process' : '',
    unresolved ? 'is-unresolved' : '',
    interactive ? 'is-interactive' : '',
    selected ? 'is-selected' : '',
    focused ? 'is-focused' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const stop = (event: MouseEvent | KeyboardEvent) => {
    event.stopPropagation();
  };

  const onBody = onActivate ?? onSelectInLineage ?? onOpenObject;

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!interactive || !onBody) {
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onBody(event as unknown as Parameters<MouseEventHandler<HTMLElement>>[0]);
    }
  };

  return (
    <div
      className={classes}
      onClick={
        interactive && onBody
          ? (event) => {
              onBody(event);
            }
          : undefined
      }
      style={
        {
          '--lineage-accent': accent,
          ...style,
        } as CSSProperties
      }
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      onKeyDown={interactive ? onKeyDown : undefined}
    >
      <div className="lineage-asset-chip__actions">
        {onSelectInLineage && !unresolved ? (
          <Tooltip title="Показать зависимости рядом">
            <button
              type="button"
              className="lineage-asset-chip__action"
              aria-label="Показать зависимости рядом"
              onClick={(event) => {
                stop(event);
                onSelectInLineage(event);
              }}
            >
              <AimOutlined />
            </button>
          </Tooltip>
        ) : null}
        {onOpenUniverse && !unresolved ? (
          <Tooltip title="Открыть в Universe">
            <button
              type="button"
              className="lineage-asset-chip__action lineage-asset-chip__action--universe"
              aria-label="Открыть в Universe"
              onClick={(event) => {
                stop(event);
                onOpenUniverse(event);
              }}
            >
              <ExperimentOutlined />
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
      <Tooltip
        title={hint ? `${title} — ${hint}` : title}
        placement="topLeft"
        mouseEnterDelay={0.2}
      >
        <div className="lineage-asset-chip__main">
          {selected ? <span className="lineage-asset-chip__current">текущий</span> : null}
          {showType ? (
            <Tag
              className="lineage-asset-chip__tag"
              color={unresolved ? 'red' : TYPE_COLOR[assetType]}
            >
              {actor ? 'PROCESS · actor' : assetType}
            </Tag>
          ) : null}
          <Typography.Text className="lineage-asset-chip__title" ellipsis>
            {title}
          </Typography.Text>
          {hint ? (
            <Typography.Text type="secondary" className="lineage-asset-chip__hint" ellipsis>
              {hint}
            </Typography.Text>
          ) : null}
          {unresolved ? (
            <Typography.Text type="danger" style={{ fontSize: 12 }}>
              unresolved
            </Typography.Text>
          ) : null}
          {children}
        </div>
      </Tooltip>
    </div>
  );
};

export default LineageAssetChip;
