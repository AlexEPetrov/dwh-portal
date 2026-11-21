/** Match picker names without making whitespace or case significant. */
export const matchesCatalogSearch = (query: string, ...names: string[]): boolean => {
    const compact = (value: string) => value.toLowerCase().replace(/\s+/gu, '');
    const needle = compact(query);
    return names.some((name) => compact(name).includes(needle));
};
