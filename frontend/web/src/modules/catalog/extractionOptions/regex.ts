export type RegexValidation = {
  ok: boolean;
  empty?: boolean;
  error?: string;
};

/** Empty draft row is allowed while editing; only non-empty patterns are syntax-checked. */
export const validateRegexPattern = (pattern: string): RegexValidation => {
  if (!pattern.trim()) {
    return { ok: true, empty: true };
  }
  try {
    void new RegExp(pattern);
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Некорректный regex',
    };
  }
};

export const compactPatternList = (
  patterns: Array<string | null | undefined> | null | undefined
): string[] => (patterns ?? []).map((item) => String(item ?? '').trim()).filter(Boolean);

export const validateRegexPatternList = (
  patterns: Array<string | null | undefined> | null | undefined
): { ok: boolean; errors: Array<string | undefined> } => {
  const list = patterns ?? [];
  const errors = list.map((item) => {
    const result = validateRegexPattern(String(item ?? ''));
    return result.ok ? undefined : result.error;
  });
  return {
    ok: errors.every((item) => !item),
    errors,
  };
};

export type RegexMatchResult =
  | { status: 'empty' }
  | { status: 'invalid'; error: string }
  | { status: 'idle' }
  | { status: 'match' }
  | { status: 'no_match' };

/** Test sample against one pattern. Empty sample → idle; empty/invalid pattern handled explicitly. */
export const matchRegexPattern = (pattern: string, sample: string): RegexMatchResult => {
  const check = validateRegexPattern(pattern);
  if (check.empty) {
    return { status: 'empty' };
  }
  if (!check.ok) {
    return { status: 'invalid', error: check.error || 'Некорректный regex' };
  }
  if (!sample) {
    return { status: 'idle' };
  }
  try {
    return new RegExp(pattern).test(sample)
      ? { status: 'match' }
      : { status: 'no_match' };
  } catch (error) {
    return {
      status: 'invalid',
      error: error instanceof Error ? error.message : 'Некорректный regex',
    };
  }
};
