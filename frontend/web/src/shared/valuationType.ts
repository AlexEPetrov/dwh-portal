export interface ValuationTypeOption {
    value: string;
}

export const normalizeValuationType = (value: unknown): string => {
    const normalized = typeof value === 'string' ? value.trim() : '';
    if (!normalized) {
        throw new Error('Введите тип расчёта');
    }
    if (![...normalized].every((character) => /[\p{L}\p{N} _.-]/u.test(character))) {
        throw new Error("Тип расчёта может содержать только буквы, цифры, пробелы, '_', '-' и '.'");
    }
    return normalized;
};

export const resolveAvailableValuationType = (
    options: ValuationTypeOption[],
    currentValue: string | null,
): string | null => (
    options.some((option) => option.value === currentValue)
        ? currentValue
        : options[0]?.value ?? null
);

export const shouldLoadValuationTypes = (
    showValuationType: boolean,
    observationDate: string,
): boolean => showValuationType && observationDate.length > 0;
