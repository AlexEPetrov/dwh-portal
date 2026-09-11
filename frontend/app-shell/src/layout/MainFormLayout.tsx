import { Card, Typography, type CardProps } from 'antd';
import type { CSSProperties, ReactNode } from 'react';

const { Title } = Typography;

export interface MainFormLayoutProps {
  title: ReactNode;
  children: ReactNode;
  header?: ReactNode;
  actions?: ReactNode;
  padding?: CSSProperties['padding'];
  cardProps?: CardProps;
}

export function MainFormLayout({
  title,
  children,
  header,
  actions,
  padding = 12,
  cardProps,
}: MainFormLayoutProps) {
  const { style: cardStyle, bodyStyle, ...restCardProps } = cardProps || {};

  return (
    <div style={{ padding, height: '100%', display: 'flex', flexDirection: 'column' }}>
      {header}

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
        <Title level={3} style={{ marginBottom: 16 }}>
          {title}
        </Title>
        {actions}
      </div>

      <Card
        {...restCardProps}
        style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', ...cardStyle }}
        bodyStyle={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', ...bodyStyle }}
      >
        {children}
      </Card>
    </div>
  );
}
