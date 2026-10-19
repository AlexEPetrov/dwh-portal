import { listAssets } from '@shared/api/generated';
import type { AssetListItem } from '@shared/api/generated';
import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Drawer,
  Form,
  Input,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useMemo, useState } from 'react';
import { FilterClear, FilterToolbar } from '../components/FilterToolbar';
import FreshnessBar from '../components/FreshnessBar';
import OptionsForm from '../extractionOptions/OptionsForm';
import '../extractionOptions/optionsForm.css';
import {
  loadExtractionSourceDraft,
  type ExtractionSourceDraft,
} from '../extractionOptions/loadDraft';
import { compactPatternList, validateRegexPatternList } from '../extractionOptions/regex';
import { extractSchemaKeyForTypeId } from '../extractionOptions/schema';
import { formatDateTime } from '../format';

const compactExtractOptions = (options: Record<string, unknown>): Record<string, unknown> => ({
  ...options,
  attachment_patterns: compactPatternList(options.attachment_patterns as string[] | undefined),
  subject_patterns: compactPatternList(options.subject_patterns as string[] | undefined),
  filename_patterns: compactPatternList(options.filename_patterns as string[] | undefined),
});

const ExtractionSourcesEditPage = () => {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<ExtractionSourceDraft | null>(null);
  const [draftLoading, setDraftLoading] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState<'active' | 'deleted'>('active');
  const [page, setPage] = useState(1);

  const assetsQuery = useQuery({
    queryKey: ['catalog', 'extraction-sources-edit', { status }],
    queryFn: () =>
      listAssets({
        type: 'EXTRACTION_SOURCE',
        status,
        source: 'extraction_registry',
        page: 1,
        pageSize: 200,
      }),
  });

  const filteredItems = useMemo(() => {
    const items = (assetsQuery.data?.items ?? []).filter(
      (item) => item.source_provider === 'extraction_registry'
    );
    const needle = q.trim().toLowerCase();
    if (!needle) {
      return items;
    }
    return items.filter((item) => {
      const haystack = [
        item.display_name,
        item.name,
        item.qualified_name,
        item.description,
        item.source_provider,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(needle);
    });
  }, [assetsQuery.data?.items, q]);

  useEffect(() => {
    setPage(1);
  }, [q, status]);

  const openEditor = async (row: AssetListItem) => {
    if (row.source_provider !== 'extraction_registry') {
      message.info('Редактор доступен только для док-источников реестра');
      return;
    }
    setSelectedId(row.id);
    setDraftLoading(true);
    setDraftError(null);
    try {
      const next = await loadExtractionSourceDraft(row.id);
      if (next.sourceProvider !== 'extraction_registry') {
        setSelectedId(null);
        setDraft(null);
        message.info('Редактор доступен только для док-источников реестра');
        return;
      }
      setDraft(next);
    } catch (error) {
      setDraft(null);
      setDraftError(error instanceof Error ? error.message : 'Не удалось открыть док-источник');
    } finally {
      setDraftLoading(false);
    }
  };

  const closeEditor = () => {
    setSelectedId(null);
    setDraft(null);
    setDraftError(null);
  };

  const patternErrors = useMemo(() => {
    if (!draft) {
      return { ok: true, messages: [] as string[] };
    }
    const messages: string[] = [];
    const checks = [
      ['Шаблоны вложений', draft.extractOptions.attachment_patterns],
      ['Шаблоны темы', draft.extractOptions.subject_patterns],
      ['Шаблоны файлов', draft.extractOptions.filename_patterns],
    ] as const;
    for (const [label, value] of checks) {
      const result = validateRegexPatternList(value as string[] | undefined);
      if (!result.ok) {
        messages.push(`${label}: некорректный regex`);
      }
    }
    return { ok: messages.length === 0, messages };
  }, [draft]);

  const columns: ColumnsType<AssetListItem> = useMemo(
    () => [
      {
        title: 'Название',
        dataIndex: 'display_name',
        render: (value, row) => value || row.name,
      },
      {
        title: 'Описание',
        dataIndex: 'description',
        ellipsis: true,
        render: (value) => value || '—',
      },
      {
        title: 'Источник',
        dataIndex: 'source_provider',
        width: 180,
        render: (value) => <Tag>{value}</Tag>,
      },
      {
        title: 'Обновлён',
        dataIndex: 'last_seen_at',
        width: 180,
        render: (value) => formatDateTime(value),
      },
      {
        title: '',
        key: 'edit',
        width: 120,
        render: (_, row) => (
          <Button
            size="small"
            type="link"
            onClick={(event) => {
              event.stopPropagation();
              void openEditor(row);
            }}
          >
            Открыть
          </Button>
        ),
      },
    ],
    []
  );

  const extractSchemaKey = extractSchemaKeyForTypeId(draft?.extractSourceTypeId);

  return (
    <Space direction="vertical" size={12} style={{ width: '100%', maxWidth: '100%', minWidth: 0 }}>
      <div>
        <Typography.Title level={2} style={{ marginBottom: 4 }}>
          Редактировать док-источники
        </Typography.Title>
        <FreshnessBar items={assetsQuery.data?.collector_freshness ?? []} />
      </div>
      {assetsQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message="Не удалось загрузить док-источники"
          description={assetsQuery.error instanceof Error ? assetsQuery.error.message : undefined}
        />
      ) : null}
      <FilterToolbar>
        <Input
          allowClear
          size="small"
          placeholder="Поиск…"
          style={{ width: 240 }}
          value={q}
          onChange={(event) => setQ(event.target.value)}
        />
        <Select
          size="small"
          style={{ width: 110 }}
          value={status}
          options={[
            { value: 'active', label: 'Active' },
            { value: 'deleted', label: 'Deleted' },
          ]}
          onChange={(value) => setStatus(value)}
        />
        <FilterClear
          visible={Boolean(q.trim())}
          onClick={() => {
            setQ('');
          }}
        />
      </FilterToolbar>
      <Table
        rowKey="id"
        loading={assetsQuery.isPending || assetsQuery.isFetching}
        columns={columns}
        dataSource={filteredItems}
        pagination={{
          current: page,
          pageSize: 25,
          total: filteredItems.length,
          onChange: setPage,
        }}
        onRow={(row) => ({
          onClick: () => {
            void openEditor(row);
          },
          style: { cursor: 'pointer' },
        })}
      />

      <Drawer
        className="extraction-source-drawer"
        width={760}
        open={Boolean(selectedId)}
        onClose={closeEditor}
        destroyOnClose
        title={draft?.name || 'Док-источник'}
        extra={
          <Button
            type="primary"
            disabled={!draft || !patternErrors.ok}
            onClick={() => {
              if (!draft) return;
              if (!patternErrors.ok) {
                message.error(patternErrors.messages.join('; '));
                return;
              }
              setDraft((prev) =>
                prev
                  ? { ...prev, extractOptions: compactExtractOptions(prev.extractOptions) }
                  : prev
              );
              message.info('Сохранение в реестр DWH будет подключено позже');
            }}
          >
            Сохранить
          </Button>
        }
      >
        {draftLoading ? <Typography.Text>Загрузка…</Typography.Text> : null}
        {draftError ? <Alert type="error" showIcon message={draftError} /> : null}
        {draft ? (
          <Space direction="vertical" size={16} style={{ width: '100%', maxWidth: '100%', minWidth: 0 }}>
            <Space wrap size={8} style={{ maxWidth: '100%' }}>
              <Tag>{draft.sourceProvider}</Tag>
              {draft.extractSourceTypeId != null ? (
                <Tag>type_id={draft.extractSourceTypeId}</Tag>
              ) : null}
              <Typography.Text
                type="secondary"
                copyable={{ text: draft.qualifiedName }}
                style={{ maxWidth: '100%', overflowWrap: 'anywhere' }}
              >
                {draft.qualifiedName}
              </Typography.Text>
            </Space>

            <Form layout="vertical" requiredMark={false}>
              <Form.Item label="Название" style={{ marginBottom: 12 }}>
                <Input
                  value={draft.name}
                  onChange={(event) =>
                    setDraft((prev) => (prev ? { ...prev, name: event.target.value } : prev))
                  }
                />
              </Form.Item>
              <Form.Item label="Описание" style={{ marginBottom: 12 }}>
                <Input.TextArea
                  value={draft.description}
                  autoSize={{ minRows: 2, maxRows: 4 }}
                  onChange={(event) =>
                    setDraft((prev) =>
                      prev ? { ...prev, description: event.target.value } : prev
                    )
                  }
                />
              </Form.Item>
              <Form.Item label="Активен" style={{ marginBottom: 0 }}>
                <Switch
                  checked={draft.isActive}
                  onChange={(checked) =>
                    setDraft((prev) => (prev ? { ...prev, isActive: checked } : prev))
                  }
                />
              </Form.Item>
            </Form>

            {!patternErrors.ok ? (
              <Alert type="error" showIcon message={patternErrors.messages.join('; ')} />
            ) : null}

            <Tabs
              items={[
                {
                  key: 'extract',
                  label: 'Извлечение',
                  children: (
                    <OptionsForm
                      schemaKey={extractSchemaKey}
                      formData={draft.extractOptions}
                      onChange={(next) =>
                        setDraft((prev) => (prev ? { ...prev, extractOptions: next } : prev))
                      }
                    />
                  ),
                },
                {
                  key: 'storage',
                  label: 'Хранение',
                  children: (
                    <OptionsForm
                      schemaKey="ExtractStorageOptions"
                      formData={draft.storageOptions}
                      onChange={(next) =>
                        setDraft((prev) => (prev ? { ...prev, storageOptions: next } : prev))
                      }
                    />
                  ),
                },
                {
                  key: 'load',
                  label: 'Загрузка',
                  children: (
                    <OptionsForm
                      schemaKey="ExtractLoadOptions"
                      formData={draft.loadOptions}
                      onChange={(next) =>
                        setDraft((prev) =>
                          prev
                            ? {
                                ...prev,
                                loadOptions: {
                                  enabled: Boolean(next.enabled ?? true),
                                  handlers: Array.isArray(next.handlers)
                                    ? (next.handlers as Array<Record<string, unknown>>)
                                    : [],
                                },
                              }
                            : prev
                        )
                      }
                    />
                  ),
                },
              ]}
            />
          </Space>
        ) : null}
      </Drawer>
    </Space>
  );
};

export default ExtractionSourcesEditPage;
