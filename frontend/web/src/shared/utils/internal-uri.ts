/**
 * Utilities for parsing and serializing URI formats used in GL Tree monitor_position and modelled_position.
 *
 * Supported URI schemes (NEW universal format):
 * - dataset://<name>?page_title=...&subheader=...&entity_name=...&metric_name=...
 * - curve://<name>
 * - contract://?gl_account=...&slug=...&counterparty=...&product=...&delivery_market=...
 * - const://<value>
 * - file://<path> (Excel source references, e.g., file://balance.xlsx!Sheet!A1:B10)
 * - python://<filename> (Python script references, e.g., python://calculate_balance.py)
 *
 * Legacy format (backward-compatible parsing only, no new generation):
 * - internal://dataset/<name>?page_title=...&subheader=...&entity_name=...&metric_name=...
 * - internal://curve/<name>
 * - internal://contracts?gl_account=...&slug=...&counterparty=...&product=...&delivery_market=...
 * - internal://constant/<value>
 */

export type InternalUriSource = 'dataset' | 'curve' | 'contract' | 'constant' | 'file' | 'python';

export interface ParsedInternalUri {
    source: InternalUriSource;
    /** Present when source === 'dataset' */
    dataset?: string;
    /** Present when source === 'curve' */
    curve?: string;
    /** Query parameters extracted from the URI */
    params: Record<string, string>;
    /** Present when source === 'constant' */
    constantValue?: string;
    /** Present when source === 'file' — the file path (e.g., balance.xlsx!Sheet!A1:B10) */
    filePath?: string;
    /** Present when source === 'python' — the script filename (e.g., calculate_balance.py) */
    scriptFilename?: string;
    /** Original raw URI string */
    raw: string;
}

// ─── New universal URI scheme prefixes ─────────────────────────────────────────

const DATASET_PREFIX = 'dataset://';
const CURVE_PREFIX = 'curve://';
const CONTRACT_PREFIX = 'contract://';
const CONST_PREFIX = 'const://';
const FILE_PREFIX = 'file://';
const PYTHON_PREFIX = 'python://';

// ─── Legacy URI scheme prefixes (backward-compatible) ─────────────────────────

const INTERNAL_PREFIX = 'internal://';

// ─── Parse ────────────────────────────────────────────────────────────────────

/**
 * Parses any supported URI format into a structured object.
 * Supports both new universal format (dataset://, curve://, contract://, const://)
 * and legacy internal:// format (backward-compatible).
 * Returns null if the value is not a valid URI.
 */
export function parseInternalUri(value: string | null | undefined): ParsedInternalUri | null {
    if (!value) {
        return null;
    }

    // Try NEW universal format first
    const newResult = parseNewFormat(value);
    if (newResult) {
        return newResult;
    }

    // Try LEGACY internal:// format
    const legacyResult = parseLegacyFormat(value);
    if (legacyResult) {
        return legacyResult;
    }

    return null;
}

function parseNewFormat(value: string): ParsedInternalUri | null {
    // dataset://<name>?<params>
    if (value.startsWith(DATASET_PREFIX)) {
        const rest = value.slice(DATASET_PREFIX.length);
        const questionMarkIndex = rest.indexOf('?');
        let dataset: string;
        let queryString = '';
        if (questionMarkIndex !== -1) {
            dataset = decodeURIComponent(rest.slice(0, questionMarkIndex));
            queryString = rest.slice(questionMarkIndex + 1);
        } else {
            dataset = decodeURIComponent(rest);
        }
        return {
            source: 'dataset',
            dataset: dataset || undefined,
            params: parseQueryString(queryString),
            raw: value,
        };
    }

    // curve://<name>
    if (value.startsWith(CURVE_PREFIX)) {
        const rest = value.slice(CURVE_PREFIX.length);
        const questionMarkIndex = rest.indexOf('?');
        let curve: string;
        let queryString = '';
        if (questionMarkIndex !== -1) {
            curve = decodeURIComponent(rest.slice(0, questionMarkIndex));
            queryString = rest.slice(questionMarkIndex + 1);
        } else {
            curve = decodeURIComponent(rest);
        }
        return {
            source: 'curve',
            curve: curve || undefined,
            params: parseQueryString(queryString),
            raw: value,
        };
    }

    // contract://?<params>
    if (value.startsWith(CONTRACT_PREFIX)) {
        const rest = value.slice(CONTRACT_PREFIX.length);
        const queryString = rest.startsWith('?') ? rest.slice(1) : rest;
        return {
            source: 'contract',
            params: parseQueryString(queryString),
            raw: value,
        };
    }

    // const://<value>
    if (value.startsWith(CONST_PREFIX)) {
        const constantValue = decodeURIComponent(value.slice(CONST_PREFIX.length));
        return {
            source: 'constant',
            params: {},
            constantValue: constantValue || undefined,
            raw: value,
        };
    }

    // file://<path>  (Excel source references)
    if (value.startsWith(FILE_PREFIX)) {
        const filePath = decodeURIComponent(value.slice(FILE_PREFIX.length));
        return {
            source: 'file',
            params: {},
            filePath: filePath || undefined,
            raw: value,
        };
    }

    // python://<filename>  (Python script references)
    if (value.startsWith(PYTHON_PREFIX)) {
        const scriptFilename = decodeURIComponent(value.slice(PYTHON_PREFIX.length));
        return {
            source: 'python',
            params: {},
            scriptFilename: scriptFilename || undefined,
            raw: value,
        };
    }

    return null;
}

function parseLegacyFormat(value: string): ParsedInternalUri | null {
    if (!value.startsWith(INTERNAL_PREFIX)) {
        return null;
    }

    const withoutPrefix = value.slice(INTERNAL_PREFIX.length);
    const questionMarkIndex = withoutPrefix.indexOf('?');
    const hashIndex = withoutPrefix.indexOf('#');

    // Determine where the path ends and query begins
    let pathEnd = withoutPrefix.length;
    if (questionMarkIndex !== -1 && questionMarkIndex < pathEnd) {
        pathEnd = questionMarkIndex;
    }
    if (hashIndex !== -1 && hashIndex < pathEnd) {
        pathEnd = hashIndex;
    }

    const path = withoutPrefix.slice(0, pathEnd);
    const remainder = withoutPrefix.slice(pathEnd);

    // Extract query string
    let queryString = '';
    if (questionMarkIndex !== -1 && remainder.startsWith('?')) {
        const queryEnd = hashIndex !== -1 && hashIndex > questionMarkIndex
            ? hashIndex - pathEnd
            : remainder.length;
        queryString = remainder.slice(1, queryEnd);
    }

    const params = parseQueryString(queryString);

    // Legacy: /dataset/<name>
    if (path.startsWith('dataset/')) {
        const dataset = path.slice('dataset/'.length);
        return {
            source: 'dataset',
            dataset: decodeURIComponent(dataset) || undefined,
            params,
            raw: value,
        };
    }

    // Legacy: /curve/<name>
    if (path.startsWith('curve/')) {
        const curve = path.slice('curve/'.length);
        return {
            source: 'curve',
            curve: decodeURIComponent(curve) || undefined,
            params,
            raw: value,
        };
    }

    // Legacy: /contracts or /contracts?<params>
    if (path === 'contracts' || path.startsWith('contracts/')) {
        return {
            source: 'contract',
            params,
            raw: value,
        };
    }

    // Legacy: /constant/<value>
    if (path.startsWith('constant/')) {
        const constantValue = path.slice('constant/'.length);
        return {
            source: 'constant',
            params,
            constantValue: decodeURIComponent(constantValue),
            raw: value,
        };
    }

    return null;
}

// ─── Serialize ────────────────────────────────────────────────────────────────

/**
 * Serializes a ParsedInternalUri back to a NEW universal format URI string.
 */
export function serializeInternalUri(parsed: ParsedInternalUri): string {
    switch (parsed.source) {
        case 'dataset':
            return createDatasetUri(parsed.dataset || '', parsed.params);
        case 'curve':
            return createCurveUri(parsed.curve || '');
        case 'contract':
            return createContractUri(parsed.params);
        case 'constant':
            return createConstantUri(parsed.constantValue || '');
        case 'file':
            return createFileUri(parsed.filePath || '');
        case 'python':
            return createPythonUri(parsed.scriptFilename || '');
        default:
            return parsed.raw;
    }
}

// ─── URI Constructors (NEW universal format) ─────────────────────────────────

/**
 * Creates a dataset:// URI.
 */
export function createDatasetUri(
    dataset: string,
    params: Record<string, string>,
): string {
    // URL-encode dataset slug — backend expects percent-encoded UTF-8.
    // Raw Cyrillic in dataset slugs works fine since they're not query param values.
    const encodedDataset = encodeURIComponent(dataset);
    const query = buildQueryString(params);
    return `${DATASET_PREFIX}${encodedDataset}${query ? '?' + query : ''}`;
}

/**
 * Creates a curve:// URI.
 */
export function createCurveUri(curve: string): string {
    return `${CURVE_PREFIX}${encodeURIComponent(curve)}`;
}

/**
 * Creates a contract:// URI with query params.
 */
export function createContractUri(
    params: Record<string, string>,
): string {
    const query = buildQueryString(params);
    return `${CONTRACT_PREFIX}${query ? '?' + query : ''}`;
}

/**
 * Creates a const:// URI.
 */
export function createConstantUri(value: string): string {
    return `${CONST_PREFIX}${encodeURIComponent(value)}`;
}

/**
 * Creates a file:// URI for Excel source references.
 */
export function createFileUri(filePath: string): string {
    return `${FILE_PREFIX}${encodeURIComponent(filePath)}`;
}

/**
 * Creates a python:// URI for Python script references.
 */
export function createPythonUri(scriptFilename: string): string {
    return `${PYTHON_PREFIX}${encodeURIComponent(scriptFilename)}`;
}

// ─── Utility functions ────────────────────────────────────────────────────────

/**
 * Checks if a value is a valid URI (new or legacy format).
 */
export function isInternalUri(value: string | null | undefined): boolean {
    return parseInternalUri(value) !== null;
}

/**
 * Returns a human-readable label for a URI.
 * Used for display in UI components.
 */
export function getInternalUriLabel(parsed: ParsedInternalUri): string {
    switch (parsed.source) {
        case 'dataset': {
            const parts: string[] = [];
            for (const key of ['page_title', 'subheader', 'entity_name', 'metric_name']) {
                if (parsed.params[key]) {
                    parts.push(parsed.params[key]);
                }
            }
            const datasetLabel = parsed.dataset || 'unknown';
            return parts.length > 0
                ? `dataset:${datasetLabel}(${parts.join(' / ')})`
                : `dataset:${datasetLabel}`;
        }
        case 'curve': {
            const parts: string[] = [];
            for (const [key, val] of Object.entries(parsed.params)) {
                parts.push(`${key}=${val}`);
            }
            const curveLabel = parsed.curve || 'unknown';
            return parts.length > 0
                ? `curve:${curveLabel}(${parts.join(', ')})`
                : `curve:${curveLabel}`;
        }
        case 'contract': {
            const parts: string[] = [];
            for (const [key, val] of Object.entries(parsed.params)) {
                parts.push(`${key}=${val}`);
            }
            return `contract(${parts.join(', ')})`;
        }
        case 'constant':
            return `constant: ${parsed.constantValue}`;
        case 'file':
            return `file: ${parsed.filePath}`;
        case 'python':
            return `python: ${parsed.scriptFilename}`;
        default:
            return parsed.raw;
    }
}

// ─── Private helpers ───────────────────────────────────────────────────────────

/**
 * Parses a query string into a flat key-value record.
 * Only takes the first value for each key (no multi-value support).
 */
function parseQueryString(query: string): Record<string, string> {
    if (!query) return {};

    const params: Record<string, string> = {};
    const pairs = query.split('&');

    for (const pair of pairs) {
        if (!pair) continue;
        const eqIndex = pair.indexOf('=');
        if (eqIndex === -1) {
            params[decodeURIComponent(pair)] = '';
        } else {
            const key = decodeURIComponent(pair.slice(0, eqIndex));
            const value = decodeURIComponent(pair.slice(eqIndex + 1));
            params[key] = value;
        }
    }

    return params;
}

/**
 * Builds a query string from a flat key-value record.
 */
function buildQueryString(params: Record<string, string>): string {
    return Object.entries(params)
        .filter(([, value]) => value !== undefined && value !== '')
        .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
        .join('&');
}
