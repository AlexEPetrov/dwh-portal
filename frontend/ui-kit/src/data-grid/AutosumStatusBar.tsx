import { useEffect, useState } from 'react';

interface AutosumValues {
  count: number;
  sum: number;
  avg: number;
  median: number;
  min: number;
  max: number;
}

export interface CellRange {
  startRowIndex: number;
  endRowIndex: number;
  startColId: string;
  endColId: string;
}

interface AutosumStatusBarProps {
  gridApi: any | null;
  cellRange?: CellRange | null;
}

/**
 * Excel-like autosum status bar for AgGrid.
 * Displays SUM, AVG, MEDIAN, MIN, MAX of selected numeric cells in the grid.
 * Supports both row selection and range selection (cell ranges).
 */
export const AutosumStatusBar = ({ gridApi, cellRange }: AutosumStatusBarProps) => {
  const [autosum, setAutosum] = useState<AutosumValues | null>(null);

  useEffect(() => {
    if (!gridApi) return;

    const calculateAutosum = (api: any, range: CellRange | null | undefined) => {
      const numericValues: number[] = [];

      // First, try to use provided cellRange (Community edition)
      if (range) {
        const colIds = api.getColumnDefs()?.map((col: any) => col.colId) || [];
        const startColIdx = colIds.indexOf(range.startColId);
        const endColIdx = colIds.indexOf(range.endColId);

        if (startColIdx !== -1 && endColIdx !== -1) {
          const selectedColIds = colIds.slice(startColIdx, endColIdx + 1);

          for (let rowIndex = range.startRowIndex; rowIndex <= range.endRowIndex; rowIndex++) {
            const rowNode = api.getDisplayedRowAtIndex(rowIndex);
            if (rowNode && rowNode.data) {
              selectedColIds.forEach((colId: string) => {
                const value = rowNode.data[colId];
                if (value !== null && value !== undefined && value !== '') {
                  const num = Number(value);
                  if (!isNaN(num) && isFinite(num)) {
                    numericValues.push(num);
                  }
                }
              });
            }
          }
        }
      } else {
        // Fallback to row selection
        const selectedNodes: any[] = [];
        api.forEachNode((node: any) => {
          if (node.selected) {
            selectedNodes.push(node);
          }
        });

        if (selectedNodes.length === 0) {
          setAutosum(null);
          return;
        }

        // Get all column IDs
        const columnIds = api.getColumnDefs()?.map((col: any) => col.colId) || [];

        selectedNodes.forEach((node: any) => {
          columnIds.forEach((colId: string) => {
            const value = node.data?.[colId];
            if (value !== null && value !== undefined && value !== '') {
              const num = Number(value);
              if (!isNaN(num) && isFinite(num)) {
                numericValues.push(num);
              }
            }
          });
        });
      }

      if (numericValues.length === 0) {
        setAutosum(null);
        return;
      }

      const count = numericValues.length;
      const sum = numericValues.reduce((acc, val) => acc + val, 0);
      const avg = sum / count;

      // Calculate median
      const sorted = [...numericValues].sort((a, b) => a - b);
      const mid = Math.floor(sorted.length / 2);
      const median = sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;

      const min = sorted[0];
      const max = sorted[sorted.length - 1];

      setAutosum({ count, sum, avg, median, min, max });
    };

    // Initial calculation
    calculateAutosum(gridApi, cellRange);

    // Listen to selection changed events (row selection)
    const handleSelectionChanged = () => {
      calculateAutosum(gridApi, cellRange);
    };

    gridApi.addEventListener('selectionChanged', handleSelectionChanged);

    // Cleanup
    return () => {
      gridApi.removeEventListener('selectionChanged', handleSelectionChanged);
    };
  }, [gridApi, cellRange]);

  const formatNumber = (val: number): string => {
    if (Number.isInteger(val)) return val.toLocaleString('ru-RU');
    return val.toLocaleString('ru-RU', { maximumFractionDigits: 4 });
  };

  if (!autosum) {
    return (
      <div className="autosum-status-bar">
        <span className="autosum-placeholder">Выберите строки для отображения статистики</span>
      </div>
    );
  }

  return (
    <div className="autosum-status-bar">
      <span className="autosum-item autosum-count">
        Строки: <strong>{autosum.count}</strong>
      </span>
      <span className="autosum-item autosum-sum">
        SUM: <strong>{formatNumber(autosum.sum)}</strong>
      </span>
      <span className="autosum-item autosum-avg">
        AVG: <strong>{formatNumber(autosum.avg)}</strong>
      </span>
      <span className="autosum-item autosum-median">
        MED: <strong>{formatNumber(autosum.median)}</strong>
      </span>
      <span className="autosum-item autosum-min">
        MIN: <strong>{formatNumber(autosum.min)}</strong>
      </span>
      <span className="autosum-item autosum-max">
        MAX: <strong>{formatNumber(autosum.max)}</strong>
      </span>
    </div>
  );
};
