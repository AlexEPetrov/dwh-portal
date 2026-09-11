import { CellClickedEvent, ColDef, GridApi, GridReadyEvent, SelectionChangedEvent } from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
import { AgGridReact } from 'ag-grid-react';
import { useCallback, useMemo, useRef, useState } from 'react';
import { AutosumStatusBar } from './AutosumStatusBar';

export interface DataGridProps<T = any> {
  rowData: T[];
  columnDefs: ColDef<T>[];
  height?: string;
  onGridReady?: (api: GridApi) => void;
  onSelectionChanged?: (selectedRows: T[]) => void;
  /**
   * Enable row selection (select entire rows).
   * When enabled, clicking on a row selects the entire row.
   */
  enableRowSelection?: boolean;
  /**
   * Enable cell range selection (select cell ranges within columns).
   * Works in Community edition via manual implementation.
   *
   * Usage:
   * - Click on a cell to select it
   * - Shift+click on another cell to select a rectangular range
   * - Ctrl+A to select all cells
   * - Ctrl+C to copy selected cells
   */
  enableRangeSelection?: boolean;
  enableStatusBar?: boolean;
  defaultColDef?: Partial<ColDef>;
}

export interface CellRange {
  startRowIndex: number;
  endRowIndex: number;
  startColId: string;
  endColId: string;
}

/**
 * Universal DataGrid component with cell selection, copy, and statistics.
 * Wraps AgGrid with common functionality.
 *
 * Selection modes (can be used independently or together):
 *
 * 1. Row Selection (enableRowSelection=true):
 *    - Click on a row to select the entire row
 *    - Ctrl+click to select multiple rows
 *    - Shift+click to select a range of rows
 *
 * 2. Range Selection (enableRangeSelection=true):
 *    - Click on a cell to select it
 *    - Shift+click on another cell to select a rectangular range
 *    - Ctrl+A to select all cells
 *    - Ctrl+C to copy selected cells
 *    - Status bar shows statistics for selected cells only
 *    - Works in AG Grid Community edition
 */
export function DataGrid<T = any>({
  rowData,
  columnDefs,
  height = '100%',
  onGridReady,
  onSelectionChanged,
  enableRowSelection = false,
  enableRangeSelection = true,
  enableStatusBar = true,
  defaultColDef,
}: DataGridProps<T>) {
  const gridRef = useRef<AgGridReact>(null);
  const [gridApi, setGridApi] = useState<GridApi | null>(null);
  const [cellRange, setCellRange] = useState<CellRange | null>(null);
  const anchorCellRef = useRef<{ rowIndex: number; colId: string } | null>(null);

  const handleGridReady = useCallback(
    (event: GridReadyEvent) => {
      setGridApi(event.api);
      onGridReady?.(event.api);
    },
    [onGridReady]
  );

  const handleSelectionChanged = useCallback(
    (event: SelectionChangedEvent) => {
      if (onSelectionChanged) {
        const selectedRows = event.api.getSelectedRows() as T[];
        onSelectionChanged(selectedRows);
      }
    },
    [onSelectionChanged]
  );

  const handleCellClicked = useCallback(
    (event: CellClickedEvent) => {
      if (!enableRangeSelection || !event.api) return;

      const rowIndex = event.rowIndex;
      const colId = event.column.getColId();

      if (rowIndex === null || rowIndex === undefined) return;

      const mouseEvent = event.event as MouseEvent;

      if (mouseEvent.shiftKey && anchorCellRef.current) {
        // Shift+click: extend range from anchor
        const colIds = event.api.getColumnDefs()?.map((c: any) => c.colId) || [];
        const startColIdx = colIds.indexOf(anchorCellRef.current.colId);
        const endColIdx = colIds.indexOf(colId);

        const minColIdx = Math.min(startColIdx, endColIdx);
        const maxColIdx = Math.max(startColIdx, endColIdx);
        const minRowIdx = Math.min(anchorCellRef.current.rowIndex, rowIndex);
        const maxRowIdx = Math.max(anchorCellRef.current.rowIndex, rowIndex);

        const newRange: CellRange = {
          startRowIndex: minRowIdx,
          endRowIndex: maxRowIdx,
          startColId: colIds[minColIdx],
          endColId: colIds[maxColIdx],
        };

        setCellRange(newRange);
        // Force grid to re-evaluate cell styles
        event.api.redrawRows();
      } else {
        // Regular click: set new anchor (deselects previous range)
        anchorCellRef.current = { rowIndex, colId };
        const newRange: CellRange = {
          startRowIndex: rowIndex,
          endRowIndex: rowIndex,
          startColId: colId,
          endColId: colId,
        };
        setCellRange(newRange);
        // Force grid to re-evaluate cell styles
        event.api.redrawRows();
      }
    },
    [enableRangeSelection]
  );

  const getCellStyle = useCallback(
    (params: any) => {
      if (!cellRange || !enableRangeSelection) return undefined;

      const rowIndex = params.node.rowIndex;
      const colId = params.column.getColId();
      const colIds = columnDefs.map((c: any) => c.colId || c.field);

      const startColIdx = colIds.indexOf(cellRange.startColId);
      const endColIdx = colIds.indexOf(cellRange.endColId);
      const currentColIdx = colIds.indexOf(colId);

      if (
        rowIndex >= cellRange.startRowIndex &&
        rowIndex <= cellRange.endRowIndex &&
        currentColIdx >= startColIdx &&
        currentColIdx <= endColIdx
      ) {
        return {
          backgroundColor: '#d4e6ff',
          border: '1px solid #1890ff'
        };
      }
      return undefined;
    },
    [cellRange, enableRangeSelection, columnDefs]
  );

  const computedDefaultColDef = useMemo(
    () => ({
      sortable: true,
      filter: true,
      resizable: true,
      flex: 1,
      minWidth: 100,
      cellStyle: getCellStyle,
      ...defaultColDef,
    }),
    [defaultColDef, getCellStyle]
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height, width: '100%' }}>
      <div className="ag-theme-alpine" style={{ flex: '1 1 0', minHeight: 0, overflow: 'hidden' }}>
        <AgGridReact
          ref={gridRef}
          rowData={rowData}
          columnDefs={columnDefs}
          defaultColDef={computedDefaultColDef}
          onGridReady={handleGridReady}
          onSelectionChanged={handleSelectionChanged}
          onCellClicked={handleCellClicked}
          rowSelection={enableRowSelection ? 'multiple' : undefined}
          suppressRowClickSelection={!enableRowSelection}
          suppressCellFocus={false}
          animateRows={true}
        />
      </div>
      {enableStatusBar && gridApi && (
        <AutosumStatusBar gridApi={gridApi} cellRange={cellRange} />
      )}
    </div>
  );
}
