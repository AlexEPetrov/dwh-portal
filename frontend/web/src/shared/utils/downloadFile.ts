import { apiClient } from '@app/core/api';
import axios from 'axios';

type DownloadRequest = {
    url: string;
    method?: 'GET' | 'POST';
    params?: Record<string, unknown>;
    data?: unknown;
    fallbackFilename: string;
};

export const downloadBlobFile = async ({
    url,
    method = 'GET',
    params,
    data,
    fallbackFilename,
}: DownloadRequest): Promise<void> => {
    let response;
    try {
        response = await apiClient.request<Blob>({
            url,
            method,
            params,
            data,
            responseType: 'blob',
            // FastAPI list query parameters use repeated keys (`markets=a&markets=b`).
            // Axios otherwise adds `[]`, so the backend does not recognize filtered exports.
            paramsSerializer: { indexes: null },
        });
    } catch (error: unknown) {
        throw await normalizeBlobDownloadError(error);
    }

    const blob = response.data;
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = filenameFromDisposition(response.headers['content-disposition']) || fallbackFilename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(objectUrl);
};

const normalizeBlobDownloadError = async (error: unknown): Promise<unknown> => {
    if (!axios.isAxiosError(error) || !(error.response?.data instanceof Blob)) {
        return error;
    }

    const text = await error.response.data.text();
    if (!text.trim()) return error;

    try {
        const body = JSON.parse(text) as { detail?: unknown };
        if (typeof body.detail === 'string' && body.detail.trim()) {
            return new Error(body.detail);
        }
        return new Error(JSON.stringify(body));
    } catch {
        return new Error(text);
    }
};

const filenameFromDisposition = (header: unknown): string | null => {
    if (typeof header !== 'string') return null;
    const utf8Match = /filename\*=UTF-8''([^;]+)/i.exec(header);
    if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1]);
    const asciiMatch = /filename="?([^";]+)"?/i.exec(header);
    return asciiMatch?.[1] || null;
};
