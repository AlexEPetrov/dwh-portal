import { getAssetLineage, listLineageRoots } from '@shared/api/generated';
import type { LineageEdge, LineageNode } from '@shared/api/generated';
import { ArrowLeftOutlined, SearchOutlined } from '@ant-design/icons';
import { Button, Empty, Input, Spin, Typography } from 'antd';
import { useCallback, useDeferredValue, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import LineageUniverseScene, {
  type UniverseOrigin,
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
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return hay.includes(query);
};

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
  const deferredQuery = useDeferredValue(query.trim().toLowerCase());
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

  const filteredNodes = useMemo(
    () => nodes.filter((node) => matchesQuery(node, deferredQuery)),
    [nodes, deferredQuery]
  );

  const filteredEdges = useMemo(() => {
    if (!deferredQuery) {
      return edges;
    }
    const ids = new Set(filteredNodes.map((node) => node.id));
    return edges.filter(
      (edge) => ids.has(edge.from_asset_id) && ids.has(edge.to_asset_id)
    );
  }, [edges, filteredNodes, deferredQuery]);

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
            autoFocus={mode === 'roots'}
          />
          <Typography.Text className="lineage-universe-search-count">
            {deferredQuery
              ? `${filteredNodes.length} из ${nodes.length}`
              : `${nodes.length} объектов`}
          </Typography.Text>
          <Typography.Paragraph className="lineage-universe-hint">
            {mode === 'roots'
              ? 'Сетка источников. Печатайте — список сразу сужается. Клик — поток источника.'
              : 'Поток слева направо. Жёлтый bridge — VIEW/TABLE из нескольких DATA_SOURCE.'}
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
                deferredQuery
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
            onSelect={onSelect}
          />
        )}
      </main>
    </div>
  );
};

export default LineageUniversePage;
