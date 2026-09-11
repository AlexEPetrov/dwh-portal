import { ApiError } from '@shared/api/generated/core/ApiError';

type ErrorDetailItem = {
    msg?: unknown;
};

type ErrorDetailContainer = {
    detail?: unknown;
};

type AxiosLikeError = {
    response?: {
        data?: unknown;
    };
};

const normalizeUnknownBody = (body: unknown): string | null => {
    if (body === undefined || body === null) {
        return null;
    }

    if (typeof body === 'string') {
        return body.trim() || null;
    }

    try {
        return JSON.stringify(body, null, 2);
    } catch {
        return String(body);
    }
};

const normalizeDetail = (detail: unknown): string | null => {
    if (typeof detail === 'string' && detail.trim()) {
        return detail;
    }

    if (Array.isArray(detail) && detail.length > 0) {
        const message = detail
            .map((item) => {
                if (typeof item === 'string') return item;
                if (item && typeof item === 'object' && 'msg' in item) {
                    return String((item as ErrorDetailItem).msg || '');
                }
                return String(item);
            })
            .filter(Boolean)
            .join('; ');

        return message || null;
    }

    return null;
};

export const extractApiErrorMessage = (error: unknown, fallback: string): string => {
    const axiosLikeData =
        error && typeof error === 'object' && 'response' in error
            ? (error as AxiosLikeError).response?.data
            : undefined;

    const axiosLikeDetail = normalizeDetail((axiosLikeData as ErrorDetailContainer | undefined)?.detail);
    if (axiosLikeDetail) {
        return axiosLikeDetail;
    }

    const axiosLikeBody = normalizeUnknownBody(axiosLikeData);
    if (axiosLikeBody) {
        return axiosLikeBody;
    }

    if (error instanceof ApiError) {
        const apiErrorDetail = normalizeDetail((error.body as ErrorDetailContainer | undefined)?.detail);
        if (apiErrorDetail) {
            return apiErrorDetail;
        }
        const apiErrorBody = normalizeUnknownBody(error.body);
        if (apiErrorBody) {
            return apiErrorBody;
        }
        if (error.message) {
            return error.message;
        }
    }

    if (error instanceof Error && error.message) {
        return error.message;
    }

    return fallback;
};
