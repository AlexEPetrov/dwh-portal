import calculationRun from './docs/calculation-run.md?raw';
import observationComparison from './docs/observation-comparison.md?raw';
import scenarioAnalysis from './docs/scenario-analysis.md?raw';
import simulationComparison from './docs/simulation-comparison.md?raw';
import valuationAnalysisFilters from './docs/valuation-analysis-filters.md?raw';
import valuationSimulationAnalysis from './docs/valuation-simulation-analysis.md?raw';

export interface HelpTopic {
    id: string;
    title: string;
    route?: string;
    content: string;
}

const HELP_TOPICS: HelpTopic[] = [
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

export const resolveHelpTopic = (pathname: string): HelpTopic | null => {
    const normalizedPathname = pathname.replace(/\/$/, '') || '/';
    return HELP_TOPICS.find((topic) => topic.route && (normalizedPathname === topic.route || normalizedPathname.startsWith(`${topic.route}/`))) ?? null;
};

export const resolveHelpTopicById = (id: string): HelpTopic | null => HELP_TOPICS.find((topic) => topic.id === id) ?? null;

export const getHelpTopics = (): HelpTopic[] => HELP_TOPICS;
