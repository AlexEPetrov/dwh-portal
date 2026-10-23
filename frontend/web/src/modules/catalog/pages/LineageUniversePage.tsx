import { getAssetLineage, listLineageRoots } from '@shared/api/generated';
import type { LineageEdge, LineageNode } from '@shared/api/generated';
import { AimOutlined, ArrowLeftOutlined, SearchOutlined } from '@ant-design/icons';
import { Button, Empty, Input, Spin, Typography } from 'antd';
import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import LineageUniverseScene, {
  type UniverseOrigin,
  type UniverseSceneControls,
} from '../components/LineageUniverseScene';
import '../components/lineageUniverse.css';

type LocationState = {
  fromRing?: UniverseOrigin;
};

const matchesQuery = (node: LineageNode, query: string) => {
  if (!query) {
    return true;
  }
  const hay = [
    node.display_name,
    node.name,
    node.qualified_name,
    node.asset_type,
    node.kind,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return hay.includes(query);
};

const letterBucket = (name: string): string => {
  const ch = (name || '?').trim().charAt(0).toLocaleUpperCase('en-US');
  if (ch >= 'A' && ch <= 'Z') {
    return ch;
  }
  return '#';
};

const startsWithChar = (name: string, ch: string) =>
  (name || '').trim().charAt(0).toLocaleLowerCase() === ch.toLocaleLowerCase();

const byDisplayName = (a: LineageNode, b: LineageNode) =>
  a.display_name.localeCompare(b.display_name) || a.id.localeCompare(b.id);

const LineageUniversePage = () => {
  const { assetId } = useParams<{ assetId?: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const mode = assetId ? 'chain' : 'roots';
  const [nodes, setNodes] = useState<LineageNode[]>([]);
  const [edges, setEdges] = useState<LineageEdge[]>([]);
  const [title, setTitle] = useState('Universe');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const deferredRaw = useDeferredValue(query.trim());
  /** 1 char → alphabet jump (no filter). 2+ → substring search. */
  const isLetterJump = deferredRaw.length === 1;
  const filterQuery = deferredRaw.length > 1 ? deferredRaw.toLowerCase() : '';
  const [focusAssetId, setFocusAssetId] = useState<string | null>(null);
  const [kindFilter, setKindFilter] = useState<string | null>(null);
  /** Pointer/keyboard inside the right rail — freeze parade; after a beat → full catalog. */
  const [listEngaged, setListEngaged] = useState(false);
  const [catalogHold, setCatalogHold] = useState(false);
  const listEngagedRef = useRef(false);
  /** Stable front-of-camera ids from the scene (roots idle parade). */
  const [paradeIds, setParadeIds] = useState<string[]>([]);
  const sceneApiRef = useRef<UniverseSceneControls | null>(null);
  const resultsListRef = useRef<HTMLUListElement>(null);
  const [enterOrigin, setEnterOrigin] = useState<UniverseOrigin | null>(() => {
    const state = location.state as LocationState | null;
    return state?.fromRing ?? null;
  });

  useEffect(() => {
    const state = location.state as LocationState | null;
    if (state?.fromRing) {
      setEnterOrigin(state.fromRing);
      navigate(location.pathname, { replace: true, state: null });
    }
  }, [location.pathname, location.state, navigate]);

  useEffect(() => {
    if (!assetId) {
      setEnterOrigin(null);
    }
  }, [assetId]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setFocusAssetId(null);
    const request = assetId ? getAssetLineage({ assetId }) : listLineageRoots();
    request
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setNodes(payload.nodes);
        setEdges(payload.edges);
        if (assetId) {
          const current = payload.nodes.find((node) => node.id === assetId);
          setTitle(current?.display_name || 'Universe');
        } else {
          setTitle('Каталог источников');
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('Не удалось загрузить lineage для Universe');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [assetId]);

  const hasKinds = useMemo(
    () => nodes.some((node) => Boolean(node.kind?.trim())),
    [nodes]
  );

  const filteredNodes = useMemo(() => {
    let list = [...nodes].sort(byDisplayName);
    if (kindFilter) {
      const key = kindFilter.toLocaleLowerCase('ru-RU');
      list = list.filter((node) => {
        const kind = node.kind?.trim();
        if (key === 'прочее') {
          return !kind;
        }
        return (kind || '').toLocaleLowerCase('ru-RU') === key;
      });
    }
    if (filterQuery) {
      list = list.filter((node) => matchesQuery(node, filterQuery));
    }
    return list;
  }, [nodes, filterQuery, kindFilter]);

  const filteredEdges = useMemo(() => {
    if (!filterQuery && !kindFilter) {
      return edges;
    }
    const ids = new Set(filteredNodes.map((node) => node.id));
    return edges.filter(
      (edge) => ids.has(edge.from_asset_id) && ids.has(edge.to_asset_id)
    );
  }, [edges, filteredNodes, filterQuery, kindFilter]);

  /**
   * List modes (compatible, priority order):
   * 1. search (2+ chars) — filtered hits
   * 2. catalog — chain mode, or dwell on the rail (~350ms)
   * 3. parade — idle roots spin: nuclei in front of the camera
   * Hovering the rail freezes parade immediately so rows stay clickable.
   */
  const listMode: 'search' | 'catalog' | 'parade' = filterQuery
    ? 'search'
    : mode === 'chain' || catalogHold
      ? 'catalog'
      : 'parade';

  useEffect(() => {
    listEngagedRef.current = listEngaged;
    if (!listEngaged || filterQuery || mode !== 'roots') {
      setCatalogHold(mode === 'chain');
      return;
    }
    const timer = window.setTimeout(() => setCatalogHold(true), 350);
    return () => window.clearTimeout(timer);
  }, [listEngaged, filterQuery, mode]);

  const displayNodes = useMemo(() => {
    if (listMode !== 'parade') {
      return filteredNodes;
    }
    if (!paradeIds.length) {
      return [];
    }
    const byId = new Map(filteredNodes.map((node) => [node.id, node]));
    return paradeIds
      .map((id) => byId.get(id))
      .filter((node): node is LineageNode => Boolean(node));
  }, [listMode, filteredNodes, paradeIds]);

  const onFrontParade = useCallback(
    (ids: string[]) => {
      if (mode !== 'roots') {
        return;
      }
      // Freeze while the pointer is on the rail (or search owns the list).
      if (listEngagedRef.current || filterQuery) {
        return;
      }
      setParadeIds(ids);
    },
    [mode, filterQuery]
  );

  useEffect(() => {
    if (!focusAssetId) {
      return;
    }
    const pool = listMode === 'parade' ? displayNodes : filteredNodes;
    if (!pool.some((node) => node.id === focusAssetId)) {
      // Parade churn must not yank focus; only search/catalog realign.
      if (listMode === 'parade') {
        return;
      }
      setFocusAssetId(pool[0]?.id ?? null);
    }
  }, [filteredNodes, displayNodes, focusAssetId, listMode]);

  // 2+ chars: focus first search hit.
  useEffect(() => {
    if (!filterQuery) {
      return;
    }
    const first = filteredNodes[0];
    if (first) {
      setFocusAssetId(first.id);
    }
  }, [filterQuery, filteredNodes]);

  // 1 char: scroll list + camera to that alphabet bucket (no filtering).
  useEffect(() => {
    if (!isLetterJump) {
      return;
    }
    const ch = deferredRaw;
    const target =
      filteredNodes.find((node) => startsWithChar(node.display_name || node.name, ch)) ??
      null;
    if (!target) {
      return;
    }
    setFocusAssetId(target.id);
    const bucket = letterBucket(target.display_name || target.name);
    sceneApiRef.current?.flyToLetter(bucket);
    const frame = requestAnimationFrame(() => {
      const row = resultsListRef.current?.querySelector<HTMLElement>(
        `[data-asset-id="${target.id}"]`
      );
      row?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    });
    return () => cancelAnimationFrame(frame);
  }, [isLetterJump, deferredRaw, filteredNodes]);

  const onSelect = useCallback(
    (id: string, origin?: UniverseOrigin) => {
      if (mode === 'roots') {
        navigate(`/lineage/universe/${id}`, {
          state: origin ? { fromRing: origin } : null,
        });
        return;
      }
      navigate(`/objects/${id}`);
    },
    [mode, navigate]
  );

  const openFocused = useCallback(() => {
    const id = focusAssetId ?? displayNodes[0]?.id ?? filteredNodes[0]?.id;
    if (id) {
      onSelect(id);
    }
  }, [focusAssetId, displayNodes, filteredNodes, onSelect]);

  const flyToFocused = useCallback(
    (id?: string) => {
      const target = id ?? focusAssetId ?? displayNodes[0]?.id ?? filteredNodes[0]?.id;
      if (!target) {
        return;
      }
      setFocusAssetId(target);
      sceneApiRef.current?.flyTo(target);
    },
    [focusAssetId, displayNodes, filteredNodes]
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)
      ) {
        return;
      }
      if (event.key === 'f' || event.key === 'F' || event.key === 'а' || event.key === 'А') {
        event.preventDefault();
        flyToFocused();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [flyToFocused]);

  const onSceneReset = useCallback(() => {
    setQuery('');
    setFocusAssetId(null);
    setKindFilter(null);
    setListEngaged(false);
    setCatalogHold(false);
    setParadeIds([]);
  }, []);

  const onFilterKind = useCallback((kind: string) => {
    if (!hasKinds) {
      return;
    }
    setKindFilter((prev) => (prev === kind ? null : kind));
    setFocusAssetId(null);
  }, [hasKinds]);

  useEffect(() => {
    if (!hasKinds && kindFilter) {
      setKindFilter(null);
    }
  }, [hasKinds, kindFilter]);

  return (
    <div className="lineage-universe-page">
      <header className="lineage-universe-top">
        <div className="lineage-universe-top__left">
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            className="lineage-universe-back"
            onClick={() =>
              navigate(assetId ? `/lineage/universe` : '/lineage')
            }
          >
            {assetId ? 'К каталогу Universe' : 'Назад к Lineage'}
          </Button>
          <div>
            <Typography.Text className="lineage-universe-kicker">UNIVERSE</Typography.Text>
            <Typography.Title level={3} className="lineage-universe-title">
              {title}
            </Typography.Title>
          </div>
        </div>
        <div className="lineage-universe-top__right">
          {!loading && !error && nodes.length > 0 ? (
            <div
              className="lineage-universe-combobox"
              role="combobox"
              aria-expanded="true"
              aria-haspopup="listbox"
              aria-controls="lineage-universe-results"
            >
              <Input
                allowClear
                size="middle"
                prefix={<SearchOutlined />}
                className="lineage-universe-search"
                placeholder={
                  mode === 'roots' ? 'Поиск источника…' : 'Фильтр объектов в потоке…'
                }
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onPressEnter={openFocused}
                autoFocus={mode === 'roots'}
                aria-autocomplete="list"
                aria-controls="lineage-universe-results"
              />
              <div
                className="lineage-universe-dropdown"
                onMouseEnter={() => setListEngaged(true)}
                onMouseLeave={() => {
                  setListEngaged(false);
                  if (!filterQuery) {
                    setFocusAssetId(null);
                  }
                }}
              >
                <div className="lineage-universe-dropdown__meta">
                  <Typography.Text className="lineage-universe-search-count">
                    {listMode === 'parade'
                      ? displayNodes.length
                        ? `Перед камерой · ${displayNodes.length}`
                        : 'Перед камерой · вращайте спираль'
                      : isLetterJump
                        ? `К букве «${deferredRaw.toLocaleUpperCase()}» · ${nodes.length} объектов`
                        : filterQuery || kindFilter
                          ? `${filteredNodes.length} из ${nodes.length}`
                          : `${nodes.length} объектов`}
                    {listMode === 'search'
                      ? ' · поиск'
                      : listMode === 'parade'
                        ? ' · parade'
                        : ' · каталог'}
                    {' · F — подлететь'}
                    {mode === 'roots' ? ' · Enter — открыть' : null}
                  </Typography.Text>
                  {kindFilter ? (
                    <button
                      type="button"
                      className="lineage-universe-kind-chip"
                      onClick={() => setKindFilter(null)}
                    >
                      KIND · {kindFilter}
                      <span aria-hidden>×</span>
                    </button>
                  ) : null}
                </div>
                {displayNodes.length ? (
                  <ul
                    ref={resultsListRef}
                    id="lineage-universe-results"
                    className="lineage-universe-results"
                    role="listbox"
                    aria-label={
                      listMode === 'parade'
                        ? 'Источники перед камерой'
                        : mode === 'roots'
                          ? 'Источники'
                          : 'Объекты потока'
                    }
                  >
                    {displayNodes.map((node) => {
                      const active = node.id === focusAssetId;
                      return (
                        <li
                          key={node.id}
                          role="option"
                          aria-selected={active}
                          data-asset-id={node.id}
                          className={
                            active
                              ? 'lineage-universe-result-row is-active'
                              : 'lineage-universe-result-row'
                          }
                        >
                          <button
                            type="button"
                            className="lineage-universe-result"
                            onMouseEnter={() => setFocusAssetId(node.id)}
                            onFocus={() => {
                              setListEngaged(true);
                              setFocusAssetId(node.id);
                            }}
                            onClick={() => onSelect(node.id)}
                          >
                            <span className="lineage-universe-result__name">
                              {node.display_name}
                            </span>
                            <span className="lineage-universe-result__meta">
                              {node.kind ? `${node.kind} · ` : ''}
                              {node.asset_type}
                              {node.extraction_source_count != null
                                ? ` · ${node.extraction_source_count} extr`
                                : ''}
                              {node.table_count != null && node.table_count > 0
                                ? ` · ${node.table_count} tbl`
                                : ''}
                            </span>
                          </button>
                          <button
                            type="button"
                            className="lineage-universe-result__fly"
                            title="Подлететь к ядру (F)"
                            aria-label={`Подлететь к ${node.display_name}`}
                            onMouseEnter={() => setFocusAssetId(node.id)}
                            onFocus={() => {
                              setListEngaged(true);
                              setFocusAssetId(node.id);
                            }}
                            onClick={(event) => {
                              event.preventDefault();
                              event.stopPropagation();
                              flyToFocused(node.id);
                            }}
                          >
                            <AimOutlined />
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <div className="lineage-universe-dropdown__empty">
                    {listMode === 'parade'
                      ? 'Подождите — ядра перед камерой появятся при вращении'
                      : 'Ничего не найдено'}
                  </div>
                )}
              </div>
            </div>
          ) : null}
          <Typography.Paragraph className="lineage-universe-hint">
            {mode === 'roots'
              ? 'Список: idle — ядра перед камерой; поиск — результаты; наведение на список — полный каталог. Прицел / F — подлёт. KIND — фильтр.'
              : 'Список: hover — подсветка, прицел — подлёт. Поток слева направо. Жёлтый bridge — VIEW/TABLE из нескольких DATA_SOURCE.'}
          </Typography.Paragraph>
        </div>
      </header>
      <main className="lineage-universe-stage">
        {loading ? (
          <div className="lineage-universe-state">
            <Spin size="large" />
          </div>
        ) : error ? (
          <div className="lineage-universe-state">
            <Empty description={error} />
          </div>
        ) : !nodes.length ? (
          <div className="lineage-universe-state">
            <Empty description="Нет объектов для Universe" />
          </div>
        ) : !filteredNodes.length ? (
          <div className="lineage-universe-state">
            <Empty
              description={
                filterQuery
                  ? `Ничего не найдено по «${query.trim()}»`
                  : 'Нет объектов для Universe'
              }
            />
          </div>
        ) : (
          <LineageUniverseScene
            nodes={filteredNodes}
            edges={filteredEdges}
            selectedAssetId={assetId}
            mode={mode}
            enterOrigin={mode === 'chain' ? enterOrigin : null}
            focusAssetId={focusAssetId}
            sceneApiRef={sceneApiRef}
            onSelect={onSelect}
            onReset={onSceneReset}
            kindFilter={hasKinds ? kindFilter : null}
            onFilterKind={mode === 'roots' && hasKinds ? onFilterKind : undefined}
            onFrontParade={mode === 'roots' ? onFrontParade : undefined}
          />
        )}
      </main>
    </div>
  );
};

export default LineageUniversePage;
