/**
 * Base fetch wrapper for all /api calls.
 * - Always uses credentials:'include' for httpOnly cookie auth.
 * - Throws ApiError with status on non-2xx responses.
 * - 401 triggers auth redirect to /login.
 */

export class ApiError extends Error {
	constructor(
		public readonly status: number,
		public readonly detail: string
	) {
		super(detail);
		this.name = 'ApiError';
	}
}

async function handleResponse<T>(res: Response): Promise<T> {
	if (res.ok) {
		// 204 No Content
		if (res.status === 204) return undefined as T;
		return res.json() as Promise<T>;
	}

	if (res.status === 401) {
		// Redirect to login if not already there
		if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
			window.location.href = '/login';
		}
		throw new ApiError(401, '인증이 필요합니다.');
	}

	let detail = res.statusText;
	try {
		const body = await res.json();
		detail = body?.detail ?? body?.message ?? detail;
	} catch {
		// ignore JSON parse failure
	}

	throw new ApiError(res.status, detail);
}

export async function apiFetch<T>(
	path: string,
	init: RequestInit = {}
): Promise<T> {
	const res = await fetch(`/api${path}`, {
		...init,
		credentials: 'include',
		headers: {
			'Content-Type': 'application/json',
			...init.headers
		}
	});
	return handleResponse<T>(res);
}

export async function apiGet<T>(path: string): Promise<T> {
	return apiFetch<T>(path, { method: 'GET' });
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
	return apiFetch<T>(path, {
		method: 'POST',
		body: body !== undefined ? JSON.stringify(body) : undefined
	});
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
	return apiFetch<T>(path, {
		method: 'PATCH',
		body: body !== undefined ? JSON.stringify(body) : undefined
	});
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
	return apiFetch<T>(path, {
		method: 'PUT',
		body: body !== undefined ? JSON.stringify(body) : undefined
	});
}

export async function apiDelete<T>(path: string, body?: unknown): Promise<T> {
	return apiFetch<T>(path, {
		method: 'DELETE',
		body: body !== undefined ? JSON.stringify(body) : undefined
	});
}
