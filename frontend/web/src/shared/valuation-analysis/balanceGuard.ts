import { getSavedMetadataApiValuationGlCalculatedTreeSavedMetadataGet } from '@shared/api/generated/services.gen';

export const BALANCE_NOT_SAVED_WARNING = 'На выбранную дату баланс не был рассчитан и сохранен';

export interface BalanceSaveGuardResult {
    ok: boolean;
    missingDates: string[];
}

export const ensureSavedBalanceAvailable = async (
    observationDates: string[],
    valuationType: string | null | undefined,
): Promise<BalanceSaveGuardResult> => {
    const uniqueDates = Array.from(new Set(observationDates.filter(Boolean)));
    const checks = await Promise.all(uniqueDates.map(async (observationDate) => {
        const coverage = await getSavedMetadataApiValuationGlCalculatedTreeSavedMetadataGet({
            observationDate,
            valuationType: valuationType || undefined,
        });
        return {
            observationDate,
            hasSavedBalance: (coverage?.items?.length || 0) > 0,
        };
    }));

    const missingDates = checks
        .filter((item) => !item.hasSavedBalance)
        .map((item) => item.observationDate);

    return {
        ok: missingDates.length === 0,
        missingDates,
    };
};
