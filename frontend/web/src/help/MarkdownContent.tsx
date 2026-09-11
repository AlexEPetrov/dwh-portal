import { Table, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React from 'react';

const { Paragraph, Text, Title } = Typography;

type Block =
  | { type: 'heading'; level: number; text: string }
  | { type: 'paragraph'; text: string }
  | { type: 'list'; items: string[] }
  | { type: 'code'; language: string; content: string }
  | { type: 'table'; headers: string[]; alignments: Array<'left' | 'right' | 'center'>; rows: string[][] };

interface MarkdownContentProps {
  content: string;
  onHelpLink?: (topicId: string) => void;
}

const parseInline = (text: string, onHelpLink?: (topicId: string) => void): React.ReactNode[] => {
  const nodes: React.ReactNode[] = [];
  const regex = /(\[[^\]]+\]\(help:[^)]+\)|\*\*[^*]+\*\*|`[^`]+`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index));
    const value = match[0];
    if (value.startsWith('[')) {
      const link = value.match(/^\[([^\]]+)\]\(help:([^)]+)\)$/);
      if (link) {
        nodes.push(
          <Typography.Link key={`${match.index}-${value}`} onClick={() => onHelpLink?.(link[2])}>
            {link[1]}
          </Typography.Link>,
        );
      }
    } else if (value.startsWith('**')) {
      nodes.push(<Text strong key={`${match.index}-${value}`}>{value.slice(2, -2)}</Text>);
    } else {
      nodes.push(<Text code key={`${match.index}-${value}`}>{value.slice(1, -1)}</Text>);
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
};

const isTableSeparator = (line: string) => /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);

const splitTableRow = (line: string) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim());

const parseTableAlignments = (line: string): Array<'left' | 'right' | 'center'> => splitTableRow(line).map((cell) => {
  const starts = cell.startsWith(':');
  const ends = cell.endsWith(':');
  if (starts && ends) return 'center';
  if (ends) return 'right';
  return 'left';
});

const parseMarkdown = (content: string): Block[] => {
  const lines = content.replace(/\r\n/g, '\n').split('\n');
  const blocks: Block[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];

    if (!line.trim()) {
      index += 1;
      continue;
    }

    const codeFence = line.match(/^```(\w+)?\s*$/);
    if (codeFence) {
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith('```')) {
        codeLines.push(lines[index]);
        index += 1;
      }
      blocks.push({ type: 'code', language: codeFence[1] ?? '', content: codeLines.join('\n') });
      index += 1;
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      blocks.push({ type: 'heading', level: heading[1].length, text: heading[2] });
      index += 1;
      continue;
    }

    if (line.trim().startsWith('|') && index + 1 < lines.length && isTableSeparator(lines[index + 1])) {
      const headers = splitTableRow(line);
      const alignments = parseTableAlignments(lines[index + 1]);
      const rows: string[][] = [];
      index += 2;
      while (index < lines.length && lines[index].trim().startsWith('|')) {
        rows.push(splitTableRow(lines[index]));
        index += 1;
      }
      blocks.push({ type: 'table', headers, alignments, rows });
      continue;
    }

    if (/^\s*-\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\s*-\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*-\s+/, '').trim());
        index += 1;
      }
      blocks.push({ type: 'list', items });
      continue;
    }

    const paragraphLines: string[] = [];
    while (
      index < lines.length
      && lines[index].trim()
      && !/^(#{1,4})\s+/.test(lines[index])
      && !/^```/.test(lines[index])
      && !/^\s*-\s+/.test(lines[index])
      && !(lines[index].trim().startsWith('|') && index + 1 < lines.length && isTableSeparator(lines[index + 1]))
    ) {
      paragraphLines.push(lines[index].trim());
      index += 1;
    }
    blocks.push({ type: 'paragraph', text: paragraphLines.join(' ') });
  }

  return blocks;
};

const renderHeading = (block: Extract<Block, { type: 'heading' }>, key: string, onHelpLink?: (topicId: string) => void) => {
  const level = Math.min(Math.max(block.level, 2), 4) as 2 | 3 | 4;
  return <Title key={key} level={level} style={{ marginTop: level === 2 ? 24 : 16 }}>{parseInline(block.text, onHelpLink)}</Title>;
};

const renderTable = (block: Extract<Block, { type: 'table' }>, key: string, onHelpLink?: (topicId: string) => void) => {
  const columns: ColumnsType<Record<string, string>> = block.headers.map((header, columnIndex) => ({
    title: header,
    dataIndex: String(columnIndex),
    key: String(columnIndex),
    align: block.alignments[columnIndex],
    render: (value: string) => <span>{parseInline(value ?? '', onHelpLink)}</span>,
  }));
  const dataSource = block.rows.map((row, rowIndex) => ({
    key: String(rowIndex),
    ...Object.fromEntries(row.map((cell, columnIndex) => [String(columnIndex), cell])),
  }));

  return <Table key={key} columns={columns} dataSource={dataSource} pagination={false} size="small" style={{ margin: '12px 0' }} />;
};

const MarkdownContent: React.FC<MarkdownContentProps> = ({ content, onHelpLink }) => {
  const blocks = parseMarkdown(content);

  return (
    <div style={{ fontSize: 14, lineHeight: 1.65 }}>
      {blocks.map((block, index) => {
        const key = `${block.type}-${index}`;
        if (block.type === 'heading') return renderHeading(block, key, onHelpLink);
        if (block.type === 'paragraph') return <Paragraph key={key}>{parseInline(block.text, onHelpLink)}</Paragraph>;
        if (block.type === 'list') return <ul key={key}>{block.items.map((item, itemIndex) => <li key={itemIndex}>{parseInline(item, onHelpLink)}</li>)}</ul>;
        if (block.type === 'code') {
          return (
            <pre key={key} style={{ background: '#f6f8fa', border: '1px solid #e5e7eb', borderRadius: 6, padding: 12, overflowX: 'auto' }}>
              <code>{block.content}</code>
            </pre>
          );
        }
        return renderTable(block, key, onHelpLink);
      })}
    </div>
  );
};

export default MarkdownContent;
