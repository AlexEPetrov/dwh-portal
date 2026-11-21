import { ExperimentOutlined, ExportOutlined } from '@ant-design/icons';
import { Tooltip, Typography } from 'antd';
import type { CSSProperties, KeyboardEvent, ReactNode } from 'react';
import { ASSET_TYPE_LABELS } from '../assetTypes';
import { TYPE_ACCENT } from './lineageFlow';

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
  /** This exact asset is displayed in the persistent inspector. */
  inspected?: boolean;
  /** Clicked asset whose dependencies are shown beside it. */
  focused?: boolean;
  interactive?: boolean;
  /** Open object card (export icon). */
  onOpenObject?: () => void;
  /** Open immersive Universe for this asset. */
  onOpenUniverse?: () => void;
  /** Click on the chip body: focus this asset in place. */
  onActivate?: () => void;
  /** Compatibility alias for the body focus action. */
  onSelectInLineage?: () => void;
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
  inspected = false,
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
    inspected ? 'is-inspected' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const onBody = onActivate ?? onSelectInLineage ?? onOpenObject;

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!interactive || !onBody) {
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      event.stopPropagation();
      onBody();
    }
  };

  return (
    <div
      className={classes}
      style={
        {
          '--lineage-accent': accent,
          ...style,
        } as CSSProperties
      }
    >
      {!unresolved && (onOpenObject || onOpenUniverse) ? (
        <div className="lineage-asset-chip__actions" onClick={(event) => event.stopPropagation()}>
          {onOpenObject ? (
            <Tooltip title="Открыть карточку">
              <button type="button" className="lineage-asset-chip__action" aria-label={`Открыть карточку: ${title}`} onClick={onOpenObject}>
                <ExportOutlined />
              </button>
            </Tooltip>
          ) : null}
          {onOpenUniverse ? (
            <Tooltip title="Открыть в Universe">
              <button type="button" className="lineage-asset-chip__action lineage-asset-chip__action--universe" aria-label={`Открыть в Universe: ${title}`} onClick={onOpenUniverse}>
                <ExperimentOutlined />
              </button>
            </Tooltip>
          ) : null}
        </div>
      ) : null}
      <Tooltip
        title={`${assetType} · ${hint ? `${title} — ${hint}` : title}`}
        placement="topLeft"
        mouseEnterDelay={0.2}
      >
        <div
          className="lineage-asset-chip__main"
          role={interactive && onBody ? 'button' : undefined}
          tabIndex={interactive && onBody ? 0 : undefined}
          onClick={interactive ? onBody : undefined}
          onKeyDown={interactive ? onKeyDown : undefined}
          aria-pressed={interactive && onBody ? focused : undefined}
        >
          <Typography.Text className="lineage-asset-chip__title" ellipsis>
            {title}
          </Typography.Text>
          <div className="lineage-asset-chip__status">
            {inspected ? (
              <span className="lineage-asset-chip__inspected">В инспекторе</span>
            ) : selected ? (
              <span className="lineage-asset-chip__route">Цепочка</span>
            ) : null}
          </div>
          {showType ? (
            <Typography.Text type="secondary" className="lineage-asset-chip__hint">
              {ASSET_TYPE_LABELS[assetType] ?? assetType}
            </Typography.Text>
          ) : null}
          {hint ? (
            <Typography.Text type="secondary" className="lineage-asset-chip__hint" ellipsis>
              {hint}
            </Typography.Text>
          ) : null}
          {unresolved ? (
            <Typography.Text type="danger" style={{ fontSize: 12 }}>
              Объект не найден в каталоге
            </Typography.Text>
          ) : null}
          {children}
        </div>
      </Tooltip>
    </div>
  );
};

export default LineageAssetChip;
