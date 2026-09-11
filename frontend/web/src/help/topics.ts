import calculationRun from './docs/calculation-run.md?raw';
import observationComparison from './docs/observation-comparison.md?raw';
import scenarioAnalysis from './docs/scenario-analysis.md?raw';
import simulationComparison from './docs/simulation-comparison.md?raw';
import valuationAnalysisFilters from './docs/valuation-analysis-filters.md?raw';
import valuationSimulationAnalysis from './docs/valuation-simulation-analysis.md?raw';

import type { HelpTopic } from '@asset-management/app-shell/help';

export const HELP_TOPICS: HelpTopic[] = [
    {
        id: 'simulation-comparison',
        title: 'Сравнение результатов симуляций',
        route: '/valuations/simulation/comparison',
        content: simulationComparison,
    },
    {
        id: 'valuation-simulation-analysis',
        title: 'Помесячно и Liquidity-at-Risk',
        route: '/valuations/simulation/analysis',
        content: valuationSimulationAnalysis,
    },
    {
        id: 'scenario-analysis',
        title: 'Scenario Analysis: методика и интерпретация',
        route: '/dashboard/sensitivity',
        content: scenarioAnalysis,
    },
    {
        id: 'observation-comparison',
        title: 'Observation Date Comparison',
        route: '/dashboard/observation-comparison',
        content: observationComparison,
    },
    {
        id: 'calculation-run',
        title: 'Запуск расчётов',
        route: '/calculations/run',
        content: calculationRun,
    },
    {
        id: 'valuation-analysis-filters',
        title: 'Верхние фильтры анализа',
        content: valuationAnalysisFilters,
    },
];
