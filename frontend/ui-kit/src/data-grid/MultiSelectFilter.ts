import { IDoesFilterPassParams, IFilterComp, IFilterParams } from 'ag-grid-community';

/**
 * Custom multi-select filter for AG Grid Community.
 * Shows checkbox list with search and Apply button.
 * Filter is applied only when user clicks Apply or closes the popup.
 */
export class MultiSelectFilter implements IFilterComp {
    private eGui!: HTMLDivElement;
    private eSelectAll!: HTMLInputElement;
    private eList!: HTMLDivElement;
    private eMiniFilter!: HTMLInputElement;
    private eApplyButton!: HTMLButtonElement;
    private filterChangedCallback: (() => void) | null = null;
    private filterModifiedCallback: (() => void) | null = null;
    private values: string[] = [];
    private selectedValues: Set<string> = new Set();
    private pendingValues: Set<string> = new Set();
    private columnId = '';

    init(params: IFilterParams) {
        this.filterChangedCallback = params.filterChangedCallback;
        this.filterModifiedCallback = params.filterModifiedCallback;
        this.columnId = params.column.getColId();

        // Collect unique values from the column
        const valuesSet = new Set<string>();
        params.api.forEachNode((node) => {
            const val = node.data?.[this.columnId];
            if (val !== null && val !== undefined) {
                valuesSet.add(String(val));
            }
        });
        this.values = Array.from(valuesSet).sort();
        this.selectedValues = new Set(this.values);
        this.pendingValues = new Set(this.values);

        this.eGui = document.createElement('div');
        this.eGui.style.padding = '8px';
        this.eGui.style.minWidth = '200px';
        this.eGui.style.display = 'flex';
        this.eGui.style.flexDirection = 'column';
        this.eGui.style.gap = '4px';

        // Mini filter input
        this.eMiniFilter = document.createElement('input');
        this.eMiniFilter.type = 'text';
        this.eMiniFilter.placeholder = 'Search...';
        this.eMiniFilter.style.width = '100%';
        this.eMiniFilter.style.padding = '4px';
        this.eMiniFilter.style.boxSizing = 'border-box';
        this.eMiniFilter.addEventListener('input', () => this.onMiniFilterChange());
        this.eGui.appendChild(this.eMiniFilter);

        // Select All checkbox
        const selectAllLabel = document.createElement('label');
        selectAllLabel.style.display = 'flex';
        selectAllLabel.style.alignItems = 'center';
        selectAllLabel.style.gap = '4px';
        selectAllLabel.style.fontWeight = '600';
        selectAllLabel.style.cursor = 'pointer';

        this.eSelectAll = document.createElement('input');
        this.eSelectAll.type = 'checkbox';
        this.eSelectAll.checked = true;
        this.eSelectAll.addEventListener('change', () => this.onSelectAllChange());
        selectAllLabel.appendChild(this.eSelectAll);
        selectAllLabel.appendChild(document.createTextNode('(Select All)'));
        this.eGui.appendChild(selectAllLabel);

        // Checkbox list
        this.eList = document.createElement('div');
        this.eList.style.maxHeight = '200px';
        this.eList.style.overflowY = 'auto';
        this.renderList();
        this.eGui.appendChild(this.eList);

        // Apply button
        this.eApplyButton = document.createElement('button');
        this.eApplyButton.textContent = 'Apply';
        this.eApplyButton.style.marginTop = '4px';
        this.eApplyButton.style.padding = '4px 8px';
        this.eApplyButton.style.cursor = 'pointer';
        this.eApplyButton.addEventListener('click', () => this.applyFilter());
        this.eGui.appendChild(this.eApplyButton);
    }

    private renderList(filterText = '') {
        this.eList.innerHTML = '';
        const lowerFilter = filterText.toLowerCase();
        this.values.forEach((val) => {
            if (lowerFilter && !val.toLowerCase().includes(lowerFilter)) return;

            const label = document.createElement('label');
            label.style.display = 'flex';
            label.style.alignItems = 'center';
            label.style.gap = '4px';
            label.style.padding = '2px 0';
            label.style.cursor = 'pointer';

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.checked = this.pendingValues.has(val);
            checkbox.addEventListener('change', () => {
                if (checkbox.checked) {
                    this.pendingValues.add(val);
                } else {
                    this.pendingValues.delete(val);
                }
                this.eSelectAll.checked = this.pendingValues.size === this.values.length;
                // Notify that filter was modified (but not applied yet)
                this.filterModifiedCallback?.();
            });
            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(val));
            this.eList.appendChild(label);
        });
    }

    private onMiniFilterChange() {
        this.renderList(this.eMiniFilter.value);
    }

    private onSelectAllChange() {
        if (this.eSelectAll.checked) {
            this.pendingValues = new Set(this.values);
        } else {
            this.pendingValues.clear();
        }
        this.renderList(this.eMiniFilter.value);
        // Notify that filter was modified (but not applied yet)
        this.filterModifiedCallback?.();
    }

    private applyFilter() {
        this.selectedValues = new Set(this.pendingValues);
        this.filterChangedCallback?.();
    }

    getGui() {
        return this.eGui;
    }

    isFilterActive() {
        return this.selectedValues.size < this.values.length;
    }

    doesFilterPass(params: IDoesFilterPassParams) {
        const nodeValue = params.node.data?.[this.columnId];
        // If value is null/undefined, it should not pass when filter is active
        if (nodeValue === null || nodeValue === undefined) {
            return !this.isFilterActive();
        }
        return this.selectedValues.has(String(nodeValue));
    }

    getModel() {
        return { selected: Array.from(this.selectedValues) };
    }

    setModel(model: { selected: string[] } | null) {
        if (model && model.selected) {
            this.selectedValues = new Set(model.selected);
            this.pendingValues = new Set(model.selected);
        } else {
            this.selectedValues = new Set(this.values);
            this.pendingValues = new Set(this.values);
        }
    }

    afterGuiAttached() {
        // Restore pending values from applied values when popup opens
        this.pendingValues = new Set(this.selectedValues);
        this.eSelectAll.checked = this.pendingValues.size === this.values.length;
        this.renderList(this.eMiniFilter.value);
    }

    destroy() { }
}
