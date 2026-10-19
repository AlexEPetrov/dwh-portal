import { CheckCircleOutlined, CloseCircleOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import type { WidgetProps } from '@rjsf/utils';
import { Button, Empty, Input, Space, Tag, Typography } from 'antd';
import { useMemo, useState } from 'react';
import { matchRegexPattern, validateRegexPattern } from './regex';

const MatchBadge = ({
  result,
}: {
  result: ReturnType<typeof matchRegexPattern>;
}) => {
  if (result.status === 'match') {
    return (
      <Tag color="success" icon={<CheckCircleOutlined />} style={{ marginInlineEnd: 0 }}>
        match
      </Tag>
    );
  }
  if (result.status === 'no_match') {
    return (
      <Tag color="error" icon={<CloseCircleOutlined />} style={{ marginInlineEnd: 0 }}>
        no match
      </Tag>
    );
  }
  if (result.status === 'invalid') {
    return (
      <Tag color="warning" style={{ marginInlineEnd: 0 }}>
        invalid
      </Tag>
    );
  }
  return (
    <Tag style={{ marginInlineEnd: 0 }}>
      —
    </Tag>
  );
};

const RegexPatternListWidget = ({ value, onChange, disabled, readonly }: WidgetProps) => {
  const patterns = Array.isArray(value) ? value.map((item) => String(item ?? '')) : [];
  const [sample, setSample] = useState('');

  const updateAt = (index: number, next: string) => {
    const copy = [...patterns];
    copy[index] = next;
    onChange(copy);
  };

  const removeAt = (index: number) => {
    onChange(patterns.filter((_, itemIndex) => itemIndex !== index));
  };

  const add = () => {
    onChange([...patterns, '']);
  };

  const overall = useMemo(() => {
    if (!sample.trim()) {
      return null;
    }
    const results = patterns.map((pattern) => matchRegexPattern(pattern, sample));
    const hasValid = results.some((item) => item.status === 'match' || item.status === 'no_match');
    if (!hasValid) {
      return null;
    }
    return results.some((item) => item.status === 'match') ? 'match' : 'no_match';
  }, [patterns, sample]);

  return (
    <Space direction="vertical" size={12} style={{ width: '100%', maxWidth: '100%', minWidth: 0 }}>
      <div
        style={{
          width: '100%',
          maxWidth: '100%',
          minWidth: 0,
          padding: 12,
          border: '1px solid #f0f0f0',
          borderRadius: 8,
          background: '#fafafa',
        }}
      >
        <Typography.Text strong style={{ display: 'block', marginBottom: 6 }}>
          Проверка строки
        </Typography.Text>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 8, fontSize: 12 }}>
          Введите пример имени файла / темы — справа у каждого шаблона будет match / no match
        </Typography.Paragraph>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', width: '100%', minWidth: 0 }}>
          <Input
            allowClear
            value={sample}
            placeholder="например: argus_products_2026-03-01.xlsx"
            onChange={(event) => setSample(event.target.value)}
            style={{
              flex: 1,
              minWidth: 0,
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
            }}
          />
          {overall === 'match' ? (
            <Tag color="success" icon={<CheckCircleOutlined />}>
              есть match
            </Tag>
          ) : null}
          {overall === 'no_match' ? (
            <Tag color="error" icon={<CloseCircleOutlined />}>
              нет match
            </Tag>
          ) : null}
        </div>
      </div>

      {patterns.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="Нет шаблонов"
          style={{ margin: '8px 0' }}
        />
      ) : (
        patterns.map((pattern, index) => {
          const check = validateRegexPattern(pattern);
          const showError = !check.ok;
          const match = matchRegexPattern(pattern, sample);
          return (
            <div key={`pattern-${index}`} style={{ width: '100%', maxWidth: '100%', minWidth: 0 }}>
              <div
                style={{
                  display: 'flex',
                  gap: 8,
                  width: '100%',
                  maxWidth: '100%',
                  minWidth: 0,
                  alignItems: 'center',
                }}
              >
                <Input
                  value={pattern}
                  disabled={disabled || readonly}
                  status={showError ? 'error' : undefined}
                  placeholder="regex, например: (?i).*brent.*\\.xlsx$"
                  onChange={(event) => updateAt(index, event.target.value)}
                  style={{
                    flex: 1,
                    minWidth: 0,
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                  }}
                />
                <MatchBadge result={match} />
                <Button
                  icon={<DeleteOutlined />}
                  disabled={disabled || readonly}
                  onClick={() => removeAt(index)}
                />
              </div>
              {showError ? (
                <Typography.Text type="danger" style={{ fontSize: 12 }}>
                  {check.error}
                </Typography.Text>
              ) : null}
            </div>
          );
        })
      )}
      <Button
        type="dashed"
        size="small"
        icon={<PlusOutlined />}
        disabled={disabled || readonly}
        onClick={add}
      >
        Добавить шаблон
      </Button>
    </Space>
  );
};

export default RegexPatternListWidget;
