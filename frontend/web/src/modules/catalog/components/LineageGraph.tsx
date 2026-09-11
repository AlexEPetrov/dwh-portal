import type { LineageEdge, LineageNode } from '@shared/api/generated';
import { Tabs } from 'antd';
import LineageListView from './LineageListView';
import LineageMapView from './LineageMapView';
import './lineageViews.css';

type Props = {
  nodes: LineageNode[];
  edges: LineageEdge[];
  /** Fill parent height (Lineage page). Embedded tabs can pass false. */
  fillHeight?: boolean;
};

/** Parallel lineage presentations: hop list and React Flow dependency map. */
const LineageGraph = ({ nodes, edges, fillHeight = true }: Props) => (
  <Tabs
    defaultActiveKey="list"
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
            <LineageListView nodes={nodes} edges={edges} />
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
            <LineageMapView nodes={nodes} edges={edges} />
          </div>
        ),
      },
    ]}
  />
);

export default LineageGraph;
