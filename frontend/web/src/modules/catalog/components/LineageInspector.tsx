import { ExperimentOutlined, ExportOutlined } from '@ant-design/icons';
import type { LineageEdge, LineageNode } from '@shared/api/generated';
import { Button, Space, Typography } from 'antd';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ASSET_TYPE_LABELS } from '../assetTypes';
import { inspectorConnections } from './lineageInspector';

type Props = {
  nodes: LineageNode[];
  edges: LineageEdge[];
  assetId?: string;
  focused: boolean;
  onFocusNode: (assetId: string) => void;
};

const LineageInspector = ({ nodes, edges, assetId, focused, onFocusNode }: Props) => {
  const navigate = useNavigate();
  const node = nodes.find((item) => item.id === assetId);
  const connections = useMemo(
    () => inspectorConnections(assetId ?? '', nodes, edges),
    [assetId, nodes, edges]
  );

  return (
    <aside className="lineage-inspector" aria-label="Инспектор объекта">
      <Typography.Title level={5} style={{ margin: 0 }}>Инспектор объекта</Typography.Title>
      {node ? (
        <>
          <Typography.Text type="secondary">{focused ? 'Выбранный объект' : 'Объект открытой цепочки'}</Typography.Text>
          <Typography.Title level={5} className="lineage-inspector__name">{node.display_name}</Typography.Title>
          <dl className="lineage-inspector__properties">
            <dt>Тип</dt>
            <dd>{ASSET_TYPE_LABELS[node.asset_type] ?? node.asset_type}</dd>
            <dt>Полное имя</dt>
            <dd>{node.qualified_name}</dd>
            {node.kind ? <><dt>Вид</dt><dd>{node.kind}</dd></> : null}
          </dl>
          {node.unresolved ? (
            <Typography.Text type="danger">Объект не найден в каталоге</Typography.Text>
          ) : (
            <Space wrap size={4}>
              <Button size="small" icon={<ExportOutlined />} onClick={() => navigate(`/objects/${node.id}`)}>Карточка</Button>
              <Button size="small" icon={<ExperimentOutlined />} onClick={() => navigate(`/lineage/universe/${node.id}`)}>Universe</Button>
            </Space>
          )}
          {(['incoming', 'outgoing'] as const).map((direction) => (
            <section key={direction} className="lineage-inspector__connections">
              <Typography.Text strong>
                {direction === 'incoming' ? 'Данные поступают от' : 'Данные передаются в'} · {connections[direction].length}
              </Typography.Text>
              {connections[direction].length ? (
                <ul>
                  {connections[direction].map(({ edge, node: neighbour }) => (
                    <li key={edge.id}>
                      <Button
                        type="link"
                        disabled={neighbour.unresolved}
                        onClick={() => onFocusNode(neighbour.id)}
                        className="lineage-inspector__neighbour"
                      >
                        {neighbour.display_name}
                      </Button>
                      <Typography.Text type="secondary" className="lineage-inspector__relation">
                        {edge.label} · {edge.relationshipType}
                        {neighbour.unresolved ? ' · объект не найден' : ''}
                      </Typography.Text>
                    </li>
                  ))}
                </ul>
              ) : <Typography.Paragraph type="secondary">Нет связей в текущем графе</Typography.Paragraph>}
            </section>
          ))}
          <Typography.Paragraph type="secondary" className="lineage-inspector__note">
            Только непосредственные связи в пределах текущего снимка и глубины обхода.
            Это не история выполнения загрузок.
          </Typography.Paragraph>
        </>
      ) : (
        <Typography.Paragraph type="secondary">
          Выберите источник, чтобы открыть цепочку. Нажмите на объект в связях или графе,
          чтобы увидеть здесь полное имя, свойства и соседние объекты.
        </Typography.Paragraph>
      )}
    </aside>
  );
};

export default LineageInspector;
