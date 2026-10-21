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

  const [focus, setFocus] = useState<{ id: string; anchorKey?: string } | null>(null);

  useEffect(() => {
    setFocus(null);
  }, [nodes, edges]);

  const onFocusNode = useCallback(
    (assetId: string, anchorKey?: string) => {
      if (rootsOverview) {
        navigate(`/lineage/${assetId}?view=${activeKey}`);
        return;
      }
      setFocus((current) => {
        const sameNode = current?.id === assetId;
        if (sameNode && (anchorKey === undefined || current.anchorKey === anchorKey)) {
          return null;
        }
        return {
          id: assetId,
          anchorKey: anchorKey ?? (sameNode ? current?.anchorKey : undefined),
        };
      });
    },
    [activeKey, navigate, rootsOverview]
  );

  const onClearFocus = useCallback(() => {
    setFocus(null);
  }, []);

  return (
    <Tabs
      activeKey={activeKey}
      onChange={(key) => setView(key === 'map' ? 'map' : 'list')}
      // Keep both panes mounted — rebuilding G6 on every tab switch is what feels slow.
      destroyInactiveTabPane={false}
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
            <div
              className={fillHeight ? 'lineage-list-scroll is-fill' : 'lineage-list-scroll'}
            >
              <LineageListView
                nodes={nodes}
                edges={edges}
                selectedAssetId={selectedAssetId}
                focusId={focus?.id ?? null}
                focusAnchorKey={focus?.anchorKey}
                onFocusNode={onFocusNode}
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
              className={fillHeight ? 'lineage-map-pane is-fill' : 'lineage-map-pane'}
            >
              <LineageMapView
                nodes={nodes}
                edges={edges}
                selectedAssetId={selectedAssetId}
                focusId={focus?.id ?? null}
                onFocusNode={onFocusNode}
                onClearFocus={onClearFocus}
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
