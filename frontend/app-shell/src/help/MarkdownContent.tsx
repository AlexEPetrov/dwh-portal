import { Typography } from 'antd';
import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const { Paragraph, Text, Title } = Typography;

export interface MarkdownContentProps {
  content: string;
  onHelpLink?: (topicId: string) => void;
  /**
   * Карта URL для изображений, на которые ссылается документ.
   * Документы справки живут вне бандла, поэтому относительные пути в них
   * не разрешаются сборщиком и требуют предварительно собранной карты.
   */
  assetUrls?: Record<string, string>;
}

const HELP_SCHEME = 'help:';

const resolveAssetUrl = (src: string, assetUrls?: Record<string, string>): string | undefined => {
  if (/^(https?:)?\/\//.test(src) || src.startsWith('data:') || src.startsWith('/')) return src;
  if (!assetUrls) return undefined;

  const normalized = src.replace(/^\.\//, '');
  if (assetUrls[normalized]) return assetUrls[normalized];

  const fileName = normalized.split('/').pop();
  return fileName ? assetUrls[fileName] : undefined;
};

const tableCellStyle: React.CSSProperties = {
  border: '1px solid #e5e7eb',
  padding: '6px 10px',
  textAlign: 'left',
  verticalAlign: 'top',
};

export const MarkdownContent: React.FC<MarkdownContentProps> = ({ content, onHelpLink, assetUrls }) => (
  <div style={{ fontSize: 14, lineHeight: 1.65 }}>
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => <Title level={2} style={{ marginTop: 24 }}>{children}</Title>,
        h2: ({ children }) => <Title level={2} style={{ marginTop: 24 }}>{children}</Title>,
        h3: ({ children }) => <Title level={3} style={{ marginTop: 16 }}>{children}</Title>,
        h4: ({ children }) => <Title level={4} style={{ marginTop: 16 }}>{children}</Title>,
        h5: ({ children }) => <Title level={5} style={{ marginTop: 16 }}>{children}</Title>,
        h6: ({ children }) => <Title level={5} style={{ marginTop: 16 }}>{children}</Title>,
        p: ({ children }) => <Paragraph>{children}</Paragraph>,
        strong: ({ children }) => <Text strong>{children}</Text>,
        em: ({ children }) => <Text italic>{children}</Text>,
        hr: () => <hr style={{ border: 0, borderTop: '1px solid #e5e7eb', margin: '20px 0' }} />,
        blockquote: ({ children }) => (
          <blockquote style={{ borderLeft: '3px solid #e5e7eb', margin: '12px 0', padding: '0 0 0 12px' }}>
            {children}
          </blockquote>
        ),
        a: ({ href, children }) => {
          if (href?.startsWith(HELP_SCHEME)) {
            const topicId = href.slice(HELP_SCHEME.length);
            return <Typography.Link onClick={() => onHelpLink?.(topicId)}>{children}</Typography.Link>;
          }
          return (
            <Typography.Link href={href} target="_blank" rel="noreferrer">
              {children}
            </Typography.Link>
          );
        },
        img: ({ src, alt }) => {
          const resolved = typeof src === 'string' ? resolveAssetUrl(src, assetUrls) : undefined;
          if (!resolved) return <Text type="secondary">{alt ? `[${alt}]` : null}</Text>;
          return (
            <img
              src={resolved}
              alt={alt ?? ''}
              style={{ maxWidth: '100%', border: '1px solid #e5e7eb', borderRadius: 6, margin: '12px 0' }}
            />
          );
        },
        code: ({ className, children }) => {
          const isBlock = Boolean(className?.startsWith('language-'));
          if (isBlock) return <code>{children}</code>;
          return <Text code>{children}</Text>;
        },
        pre: ({ children }) => (
          <pre
            style={{
              background: '#f6f8fa',
              border: '1px solid #e5e7eb',
              borderRadius: 6,
              padding: 12,
              overflowX: 'auto',
            }}
          >
            {children}
          </pre>
        ),
        table: ({ children }) => (
          <div style={{ overflowX: 'auto', margin: '12px 0' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>{children}</table>
          </div>
        ),
        th: ({ children, style }) => (
          <th style={{ ...tableCellStyle, background: '#fafafa', fontWeight: 600, textAlign: style?.textAlign ?? 'left' }}>
            {children}
          </th>
        ),
        td: ({ children, style }) => (
          <td style={{ ...tableCellStyle, textAlign: style?.textAlign ?? 'left' }}>{children}</td>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  </div>
);
