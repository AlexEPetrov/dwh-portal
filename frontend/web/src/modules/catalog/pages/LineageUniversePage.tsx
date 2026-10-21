import { getAssetLineage, listLineageRoots } from '@shared/api/generated';
import type { LineageEdge, LineageNode } from '@shared/api/generated';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { Button, Empty, Spin, Typography } from 'antd';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import LineageUniverseScene from '../components/LineageUniverseScene';
import '../components/lineageUniverse.css';

const LineageUniversePage = () => {
  const { assetId } = useParams<{ assetId?: string }>();
  const navigate = useNavigate();
  const mode = assetId ? 'chain' : 'roots';
  const [nodes, setNodes] = useState<LineageNode[]>([]);
  const [edges, setEdges] = useState<LineageEdge[]>([]);
  const [title, setTitle] = useState('Universe');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  const onSelect = useCallback(
    (id: string) => {
      if (mode === 'roots') {
        navigate(`/lineage/universe/${id}`);
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
        <Typography.Paragraph className="lineage-universe-hint">
          {mode === 'roots'
            ? 'Источники на прямоугольной сетке, дети вокруг каждого. Reset — подогнать под экран. Клик — цепочка.'
            : 'Цепочка разложена вокруг источника. Move / Zoom на панели; Reset — весь граф на экран.'}
        </Typography.Paragraph>
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
        ) : (
          <LineageUniverseScene
            nodes={nodes}
            edges={edges}
            selectedAssetId={assetId}
            mode={mode}
            onSelect={onSelect}
          />
        )}
      </main>
    </div>
  );
};

export default LineageUniversePage;
