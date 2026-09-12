import type { LineageEdge, LineageNode } from '@shared/api/generated';
import { Tabs } from 'antd';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import LineageListView from './LineageListView';
import LineageMapView from './LineageMapView';
import './lineageViews.css';

type ViewKey = 'list' | 'map';

type Props = {
  nodes: LineageNode[];
  edges: LineageEdge[];
  /** Currently focused lineage asset (page route id). */
  selectedAssetId?: string;
  /** Fill parent height (Lineage page). Embedded tabs can pass false. */
  fillHeight?: boolean;
  /**
   * Persist list/map in `?view=list|map` so browser Back from an object card
   * restores the same Lineage tab.
   */
  syncViewInUrl?: boolean;
  /** Isolated DATA_SOURCE / orphan EXTRACTION_SOURCE overview (no edges). */
  rootsOverview?: boolean;
};

const parseView = (raw: string | null): ViewKey => (raw === 'map' ? 'map' : 'list');

/** Parallel lineage presentations: hop list and React Flow dependency map. */
const LineageGraph = ({
  nodes,
  edges,
  selectedAssetId,
  fillHeight = true,
  syncViewInUrl = false,
  rootsOverview = false,
}: Props) => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [localView, setLocalView] = useState<ViewKey>('list');
  const activeKey: ViewKey = syncViewInUrl ? parseView(searchParams.get('view')) : localView;

  useEffect(() => {
    if (!syncViewInUrl) {
      return;
    }
    const raw = searchParams.get('view');
    if (raw === 'list' || raw === 'map') {
      return;
    }
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set('view', 'list');
        return next;
      },
      { replace: true }
    );
  }, [syncViewInUrl, searchParams, setSearchParams]);

  const setView = (key: ViewKey) => {
    if (!syncViewInUrl) {
      setLocalView(key);
      return;
    }
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set('view', key);
        return next;
      },
      { replace: false }
    );
  };

  const onSelectInLineage = useCallback(
    (assetId: string) => {
      const view = activeKey;
      navigate(`/lineage/${assetId}?view=${view}`);
    },
    [activeKey, navigate]
  );

  return (
    <Tabs
      activeKey={activeKey}
      onChange={(key) => setView(key === 'map' ? 'map' : 'list')}
      className={fillHeight ? 'lineage-views-tabs fill-height' : 'lineage-views-tabs'}
      style={
        fillHeight
          ? {
              flex: 1,
              minHeight: 0,
              display: 'flex',
              flexDirection: 'column',
              height: '100%',
            }
          : undefined
      }
      items={[
        {
          key: 'list',
          label: 'Список',
          children: (
            <div style={fillHeight ? { flex: 1, minHeight: 0, overflow: 'auto' } : undefined}>
              <LineageListView
                nodes={nodes}
                edges={edges}
                selectedAssetId={selectedAssetId}
                onSelectInLineage={onSelectInLineage}
                rootsOverview={rootsOverview}
              />
            </div>
          ),
        },
        {
          key: 'map',
          label: 'Граф',
          children: (
            <div
              style={
                fillHeight
                  ? { flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', height: '100%' }
                  : { height: 'min(70vh, 720px)', display: 'flex', flexDirection: 'column' }
              }
            >
              <LineageMapView
                nodes={nodes}
                edges={edges}
                selectedAssetId={selectedAssetId}
                onSelectInLineage={onSelectInLineage}
                rootsOverview={rootsOverview}
              />
            </div>
          ),
        },
      ]}
    />
  );
};

export default LineageGraph;
