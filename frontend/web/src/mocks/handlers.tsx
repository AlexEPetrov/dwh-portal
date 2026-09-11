import { http, HttpResponse } from 'msw';
import { mockContracts } from './data/contracts';

// Mock valuation runs data
const mockValuationRuns = [
  {
    id: 'run-2024-001',
    status: 'completed' as const,
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    completed_at: new Date(Date.now() - 1.8 * 60 * 60 * 1000).toISOString(),
    initiated_by: 'ivanov@a',
    curve_count: 12,
  },
  {
    id: 'run-2024-002',
    status: 'completed' as const,
    created_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    completed_at: new Date(Date.now() - 23.5 * 60 * 60 * 1000).toISOString(),
    initiated_by: 'petrov@a',
    curve_count: 8,
  },
  {
    id: 'run-2024-003',
    status: 'failed' as const,
    created_at: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(),
    completed_at: new Date(Date.now() - 47.9 * 60 * 60 * 1000).toISOString(),
    initiated_by: 'sidorov@a',
    curve_count: 5,
    error_message: 'Не удалось загрузить кривую TTF: источник недоступен',
  },
  {
    id: 'run-2024-004',
    status: 'running' as const,
    created_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    initiated_by: 'ivanov@a',
    curve_count: 15,
  },
  {
    id: 'run-2024-005',
    status: 'created' as const,
    created_at: new Date(Date.now() - 1 * 60 * 1000).toISOString(),
    initiated_by: 'system',
    curve_count: 20,
  },
];

export const handlers = [
  // GET /api/management/contracts/
  // игнорируем query-параметры:
  //http.get('/api/management/contracts/', ({ request }) => {
  //  console.log('MSW: contracts list intercepted');
  //  return HttpResponse.json(mockContracts);
  //}),
  http.get('/api/management/contracts*', () => {
    return HttpResponse.json(mockContracts);
  }),

  // GET /api/management/contracts/:slug
  http.get('/api/management/contracts/:slug', ({ params }) => {
    const contract = mockContracts.find(c => c.slug === params.slug);
    if (!contract) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(contract);
  }),

  // PUT /api/management/contracts/:slug
  http.put('/api/management/contracts/:slug', async ({ request, params }) => {
    const body = await request.json();
    const index = mockContracts.findIndex(c => c.slug === params.slug);
    if (index !== -1) {
      mockContracts[index] = { ...mockContracts[index] as Record<string, unknown>, ...(body as Record<string, unknown>) };
      return HttpResponse.json(mockContracts[index]);
    }
    return new HttpResponse(null, { status: 404 });
  }),

  // GET /api/management/curves/
  http.get('/api/management/curves/', () => {
    return HttpResponse.json([
      { slug: 'ttf', name: 'TTF Gas' },
      { slug: 'brent', name: 'Brent Crude' },
    ]);
  }),

  // GET /api/valuation/curves/:slug/values/json
  http.get('/api/valuation/curves/:slug/values/json', ({ request }) => {
    const url = new URL(request.url);
    const minDate = url.searchParams.get('min_date');
    const maxDate = url.searchParams.get('max_date');
    // Генерируем моковые данные временного ряда
    const start = new Date(minDate || '2024-01-01');
    const end = new Date(maxDate || '2024-12-31');
    const points = [];
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      points.push({
        date: d.toISOString().split('T')[0],
        value: Math.round((50 + Math.random() * 50) * 100) / 100,
      });
    }
    return HttpResponse.json(points);
  }),

  // POST /api/valuation/runs/batch
  http.post('/api/valuation/runs/batch', () => {
    return HttpResponse.json({ id: 'run-123', status: 'pending' });
  }),

  // GET /api/valuations/runs — list all runs
  http.get('/api/valuations/runs', () => {
    return HttpResponse.json(mockValuationRuns);
  }),

  // GET /api/valuations/runs/:id — single run detail
  http.get('/api/valuations/runs/:id', ({ params }) => {
    const run = mockValuationRuns.find(r => r.id === params.id);
    if (!run) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(run);
  }),

  // GET /api/valuation/runs/
  http.get('/api/valuation/runs/', () => {
    return HttpResponse.json([
      { id: 'run-1', status: 'completed', created_at: new Date().toISOString() },
      { id: 'run-2', status: 'running', created_at: new Date().toISOString() },
    ]);
  }),

  // GET /api/valuation/runs/latest/result
  http.get('/api/valuation/runs/latest/result', () => {
    const dates = Array.from({ length: 30 }, (_, i) => {
      const d = new Date();
      d.setDate(d.getDate() - 30 + i);
      return d.toISOString().split('T')[0];
    });
    const values = dates.map(() => Math.random() * 100);
    return HttpResponse.json(dates.map((date, i) => ({ date, value: values[i] })));
  }),

  // POST /api/management/uploads (загрузка контрактов)
  http.post('/api/management/uploads', async () => {
    // В реальности здесь парсинг файла и добавление в БД
    // Для мока просто вернём успех
    return HttpResponse.json({ status: 'ok', message: 'Файл принят' });
  }),

  // в handlers.ts добавить:
  http.get('/api/management/contracts/template', () => {
    // Вернём пустой xlsx файл (можно заглушку)
    return new HttpResponse('template content', {
      headers: {
        'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'Content-Disposition': 'attachment; filename="contract_template.xlsx"',
      },
    });
  }),

];
