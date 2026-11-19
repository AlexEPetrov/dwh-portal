import type { LineageResponse } from '@shared/api/generated';
import { Alert } from 'antd';
import { useState } from 'react';

type Props = {
  targets: LineageResponse['unresolved_targets'];
};

const UnresolvedTargetsAlert = ({ targets }: Props) => {
  const [expanded, setExpanded] = useState(false);
  if (!targets.length) return null;

  return (
    <Alert
      type="warning"
      showIcon
      message={`Нерешённые цели в графе: ${targets.length}`}
      style={{ flex: '0 0 auto' }}
      description={
        <details onToggle={(event) => setExpanded(event.currentTarget.open)}>
          <summary style={{ cursor: 'pointer' }}>Показать список целей</summary>
          {expanded ? (
            <div>
              <p>Цели из показанного окружения lineage не сопоставлены с объектами каталога. Они могут относиться к связанным процессам, а не только к выбранному источнику.</p>
              <ul style={{ maxHeight: 200, overflow: 'auto', overflowWrap: 'anywhere', paddingLeft: 20, marginBottom: 0 }}>
                {targets.map((target) => (
                  <li key={target.asset_id}>{target.qualified_name}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </details>
      }
    />
  );
};

export default UnresolvedTargetsAlert;
