import { Tag, Typography } from 'antd';
import type { CSSProperties, KeyboardEvent, MouseEventHandler, ReactNode } from 'react';
import { TYPE_ACCENT, TYPE_COLOR, TYPE_WASH } from './lineageFlow';

type Props = {
  assetType: string;
  title: string;
  unresolved?: boolean;
  /** PROCESS as transition actor — same dashed treatment in list and graph. */
  actor?: boolean;
  interactive?: boolean;
  onClick?: MouseEventHandler<HTMLDivElement>;
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
};

const LineageAssetChip = ({
  assetType,
  title,
  unresolved = false,
  actor = false,
  interactive = false,
  onClick,
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
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!interactive || !onClick) {
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onClick(event as unknown as Parameters<MouseEventHandler<HTMLDivElement>>[0]);
    }
  };

  return (
    <div
      className={classes}
      onClick={onClick}
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
