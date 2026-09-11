/**
 * Unit tests for internal-uri utilities.
 *
 * Run with: npx tsx internal-uri.test.ts
 * (or any test runner that supports ESM + TypeScript)
 */

import {
    createConstantUri,
    createContractUri,
    createCurveUri,
    createDatasetUri,
    getInternalUriLabel,
    isInternalUri,
    parseInternalUri,
    serializeInternalUri,
} from './internal-uri';

// ─── Minimal test harness ──────────────────────────────────────────────────────

let passed = 0;
let failed = 0;

function assert(condition: boolean, message: string): void {
    if (condition) {
        passed++;
    } else {
        failed++;
        console.error(`  FAIL: ${message}`);
    }
}

function deepEqual(a: unknown, b: unknown): boolean {
    return JSON.stringify(a) === JSON.stringify(b);
}

function test(name: string, fn: () => void): void {
    try {
        fn();
        console.log(`  PASS: ${name}`);
    } catch (e) {
        failed++;
        console.error(`  FAIL: ${name} — ${e}`);
    }
}

function describe(_name: string, fn: () => void): void {
    console.log(`\n${_name}`);
    fn();
}

// ─── Tests ─────────────────────────────────────────────────────────────────────

describe('parseInternalUri', () => {
    test('returns null for null/undefined/empty', () => {
        assert(parseInternalUri(null) === null, 'null');
        assert(parseInternalUri(undefined) === null, 'undefined');
        assert(parseInternalUri('') === null, 'empty');
    });

    test('returns null for non-internal URIs', () => {
        assert(parseInternalUri('https://example.com') === null, 'https');
        assert(parseInternalUri('["page", "subheader"]') === null, 'json array');
    });

    test('parses NEW dataset URI with all params', () => {
        const result = parseInternalUri(
            'dataset://DATASET_MONITORING?page_title=Balance%20Sheet&subheader=Assets&entity_name=OOO%20Example&metric_name=Volume',
        );
        assert(result !== null, 'not null');
        assert(result!.source === 'dataset', 'source=dataset');
        assert(result!.dataset === 'DATASET_MONITORING', 'dataset name');
        assert(
            deepEqual(result!.params, {
                page_title: 'Balance Sheet',
                subheader: 'Assets',
                entity_name: 'OOO Example',
                metric_name: 'Volume',
            }),
            'params',
        );
    });

    test('parses dataset URI with partial params', () => {
        const result = parseInternalUri(
            'dataset://DATASET_MONITORING?page_title=Balance%20Sheet',
        );
        assert(result !== null, 'not null');
        assert(result!.source === 'dataset', 'source=dataset');
        assert(result!.dataset === 'DATASET_MONITORING', 'dataset name');
        assert(deepEqual(result!.params, { page_title: 'Balance Sheet' }), 'params');
    });

    test('parses NEW contract URI with params', () => {
        const result = parseInternalUri(
            'contract://?gl_account=GL_TAX_1&slug=CONTRACT_AGPZ_2024',
        );
        assert(result !== null, 'not null');
        assert(result!.source === 'contract', 'source=contract');
        assert(
            deepEqual(result!.params, {
                gl_account: 'GL_TAX_1',
                slug: 'CONTRACT_AGPZ_2024',
            }),
            'params',
        );
    });

    test('parses contract URI without params', () => {
        const result = parseInternalUri('contract://');
        assert(result !== null, 'not null');
        assert(result!.source === 'contract', 'source=contract');
        assert(deepEqual(result!.params, {}), 'empty params');
    });

    test('parses contract URI with unknown keys', () => {
        const result = parseInternalUri('contract://?gl_ccoun=123');
        assert(result !== null, 'not null');
        assert(result!.source === 'contract', 'source=contract');
        assert(
            deepEqual(result!.params, { gl_ccoun: '123' }),
            'params with unknown key',
        );
    });

    test('parses constant URI', () => {
        const result = parseInternalUri('const://12345.67');
        assert(result !== null, 'not null');
        assert(result!.source === 'constant', 'source=constant');
        assert(result!.constantValue === '12345.67', 'constantValue');
    });

    test('parses constant URI with special chars', () => {
        const result = parseInternalUri('const://hello%20world');
        assert(result !== null, 'not null');
        assert(result!.source === 'constant', 'source=constant');
        assert(result!.constantValue === 'hello world', 'decoded value');
    });

    test('parses curve URI', () => {
        const result = parseInternalUri('curve://WAC_GAS');
        assert(result !== null, 'not null');
        assert(result!.source === 'curve', 'source=curve');
        assert(result!.curve === 'WAC_GAS', 'curve name');
    });

    test('parses curve URI with params', () => {
        const result = parseInternalUri('curve://WAC_GAS?date=2024-01-01');
        assert(result !== null, 'not null');
        assert(result!.source === 'curve', 'source=curve');
        assert(result!.curve === 'WAC_GAS', 'curve name');
        assert(deepEqual(result!.params, { date: '2024-01-01' }), 'params');
    });

    test('returns null for unknown dataset:// path', () => {
        assert(parseInternalUri('dataset://') === null, 'empty dataset');
    });

    test('returns null for unknown curve:// path', () => {
        assert(parseInternalUri('curve://') === null, 'empty curve');
    });
});

describe('serializeInternalUri', () => {
    test('serializes NEW dataset URI', () => {
        const parsed = parseInternalUri(
            'dataset://DATASET_MONITORING?page_title=Test',
        )!;
        const serialized = serializeInternalUri(parsed);
        assert(serialized.startsWith('dataset://DATASET_MONITORING?page_title=Test'), serialized);
    });

    test('serializes NEW contract URI', () => {
        const parsed = parseInternalUri('contract://?gl_account=GL_1')!;
        const serialized = serializeInternalUri(parsed);
        assert(serialized.startsWith('contract://gl_account=GL_1'), serialized);
    });

    test('serializes constant URI', () => {
        const parsed = parseInternalUri('const://42')!;
        const serialized = serializeInternalUri(parsed);
        assert(serialized === 'const://42', serialized);
    });

    test('serializes curve URI', () => {
        const parsed = parseInternalUri('curve://WAC_GAS')!;
        const serialized = serializeInternalUri(parsed);
        assert(serialized === 'curve://WAC_GAS', serialized);
    });
});

describe('createDatasetUri', () => {
    test('creates URI with all params', () => {
        const uri = createDatasetUri('DATASET_MONITORING', {
            page_title: 'Balance Sheet',
            subheader: 'Assets',
            entity_name: 'OOO Example',
            metric_name: 'Volume',
        });
        assert(
            uri ===
            'dataset://DATASET_MONITORING?page_title=Balance%20Sheet&subheader=Assets&entity_name=OOO%20Example&metric_name=Volume',
            uri,
        );
    });

    test('creates URI with no params', () => {
        const uri = createDatasetUri('DATASET_MONITORING', {});
        assert(uri === 'dataset://DATASET_MONITORING', uri);
    });
});

describe('createContractUri', () => {
    test('creates URI with params', () => {
        const uri = createContractUri({
            gl_account: 'GL_TAX_1',
            counterparty: 'GAZPROM',
        });
        assert(
            uri === 'contract://gl_account=GL_TAX_1&counterparty=GAZPROM',
            uri,
        );
    });

    test('creates URI with no params', () => {
        const uri = createContractUri({});
        assert(uri === 'contract://', uri);
    });
});

describe('createCurveUri', () => {
    test('creates URI with curve slug', () => {
        const uri = createCurveUri('WAC_GAS');
        assert(uri === 'curve://WAC_GAS', uri);
    });

    test('creates URI with encoded curve slug', () => {
        const uri = createCurveUri('WAC GAS');
        assert(uri === 'curve://WAC%20GAS', uri);
    });
});

describe('createConstantUri', () => {
    test('creates URI with value', () => {
        assert(createConstantUri('12345.67') === 'const://12345.67', 'value');
    });

    test('encodes special characters', () => {
        assert(
            createConstantUri('hello world') === 'const://hello%20world',
            'encoded',
        );
    });
});

describe('isInternalUri', () => {
    test('returns true for valid internal URIs', () => {
        assert(isInternalUri('dataset://DATASET_MONITORING') === true, 'dataset');
        assert(isInternalUri('contract://?gl_account=GL_1') === true, 'contract');
        assert(isInternalUri('curve://WAC_GAS') === true, 'curve');
        assert(isInternalUri('const://42') === true, 'constant');
    });

    test('returns false for invalid values', () => {
        assert(isInternalUri(null) === false, 'null');
        assert(isInternalUri(undefined) === false, 'undefined');
        assert(isInternalUri('') === false, 'empty');
        assert(isInternalUri('["page", "subheader"]') === false, 'json');
        assert(isInternalUri('https://example.com') === false, 'https');
    });
});

describe('getInternalUriLabel', () => {
    test('returns label for NEW dataset URI with all params', () => {
        const parsed = parseInternalUri(
            'dataset://DATASET_MONITORING?page_title=Balance%20Sheet&subheader=Assets&entity_name=OOO&metric_name=Volume',
        )!;
        assert(
            getInternalUriLabel(parsed) ===
            'dataset:DATASET_MONITORING(Balance Sheet / Assets / OOO / Volume)',
            getInternalUriLabel(parsed),
        );
    });

    test('returns label for NEW dataset URI with partial params', () => {
        const parsed = parseInternalUri(
            'dataset://DATASET_MONITORING?page_title=Balance%20Sheet',
        )!;
        assert(
            getInternalUriLabel(parsed) === 'dataset:DATASET_MONITORING(Balance Sheet)',
            getInternalUriLabel(parsed),
        );
    });

    test('returns label for NEW contract URI', () => {
        const parsed = parseInternalUri(
            'contract://?gl_account=GL_TAX_1&slug=CONTRACT_1',
        )!;
        assert(
            getInternalUriLabel(parsed) === 'contract(gl_account=GL_TAX_1, slug=CONTRACT_1)',
            getInternalUriLabel(parsed),
        );
    });

    test('returns label for curve URI', () => {
        const parsed = parseInternalUri('curve://WAC_GAS')!;
        assert(getInternalUriLabel(parsed) === 'curve:WAC_GAS', getInternalUriLabel(parsed));
    });

    test('returns label for constant URI', () => {
        const parsed = parseInternalUri('const://42')!;
        assert(getInternalUriLabel(parsed) === 'constant: 42', getInternalUriLabel(parsed));
    });
});

// ─── Summary ───────────────────────────────────────────────────────────────────

console.log(`\n─────────────────────────────────────────`);
console.log(`Results: ${passed} passed, ${failed} failed`);
if (failed > 0) {
    throw new Error(`${failed} test(s) failed`);
}
