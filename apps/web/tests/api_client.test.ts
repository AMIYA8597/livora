import test from 'node:test';
import assert from 'node:assert';
import { apiClient, ApiError, NetworkError, API_BASE_URL, refreshAccessToken } from '../lib/api-client.ts';

// Mock localStorage for Node test environment
class MockLocalStorage {
  private store: Record<string, string> = {};
  getItem(key: string): string | null {
    return this.store[key] || null;
  }
  setItem(key: string, value: string): void {
    this.store[key] = String(value);
  }
  removeItem(key: string): void {
    delete this.store[key];
  }
  clear(): void {
    this.store = {};
  }
}

// Setup mock window & localStorage
const mockStorage = new MockLocalStorage();
(globalThis as any).window = {
  dispatchEvent: (event: any) => {},
};
(globalThis as any).localStorage = mockStorage;
(globalThis as any).CustomEvent = class {
  type: string;
  constructor(type: string) {
    this.type = type;
  }
};

test('ApiError correctly structures RFC 7807 Problem Details', () => {
  const err = new ApiError({
    status: 400,
    title: 'Bad Request',
    detail: 'Invalid monthly rent constraint',
    errorCode: 'INVALID_RENT',
    instance: '/api/v1/properties/',
    invalidParams: [{ name: 'monthly_rent', reason: 'Must be greater than 0' }],
    requestId: 'req-test-123',
  });

  assert.strictEqual(err.name, 'ApiError');
  assert.strictEqual(err.status, 400);
  assert.strictEqual(err.title, 'Bad Request');
  assert.strictEqual(err.detail, 'Invalid monthly rent constraint');
  assert.strictEqual(err.errorCode, 'INVALID_RENT');
  assert.strictEqual(err.instance, '/api/v1/properties/');
  assert.strictEqual(err.requestId, 'req-test-123');
  assert.strictEqual(err.invalidParams?.length, 1);
  assert.strictEqual(err.invalidParams[0].name, 'monthly_rent');
});

test('apiClient builds query parameters correctly and omits null/undefined', async () => {
  let capturedUrl = '';
  const originalFetch = globalThis.fetch;

  globalThis.fetch = (async (url: string | URL | Request) => {
    capturedUrl = String(url);
    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }) as any;

  try {
    await apiClient('/properties', {
      params: {
        city: 'Bengaluru',
        max_rent: 35000,
        unwanted: undefined,
        empty: null,
      },
    });

    assert.ok(capturedUrl.includes('city=Bengaluru'));
    assert.ok(capturedUrl.includes('max_rent=35000'));
    assert.ok(!capturedUrl.includes('unwanted'));
    assert.ok(!capturedUrl.includes('empty'));
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('apiClient automatically adds Authorization header when token exists', async () => {
  mockStorage.setItem('flatmate_access_token', 'test_jwt_access_token_123');
  let capturedHeaders: any = {};
  const originalFetch = globalThis.fetch;

  globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
    capturedHeaders = init?.headers || {};
    return new Response(JSON.stringify({ id: 'user-1' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }) as any;

  try {
    await apiClient('/auth/me');
    assert.strictEqual(capturedHeaders['Authorization'], 'Bearer test_jwt_access_token_123');
  } finally {
    globalThis.fetch = originalFetch;
    mockStorage.clear();
  }
});

test('apiClient throws ApiError on 404 or 400 backend responses', async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = (async () => {
    return new Response(
      JSON.stringify({
        title: 'Not Found',
        status: 404,
        detail: 'Property listing not found',
        error_code: 'NOT_FOUND',
      }),
      {
        status: 404,
        headers: { 'Content-Type': 'application/problem+json', 'X-Request-ID': 'req-404' },
      }
    );
  }) as any;

  try {
    await assert.rejects(
      async () => {
        await apiClient('/properties/non-existent-id');
      },
      (err: any) => {
        assert.ok(err instanceof ApiError);
        assert.strictEqual(err.status, 404);
        assert.strictEqual(err.detail, 'Property listing not found');
        assert.strictEqual(err.requestId, 'req-404');
        return true;
      }
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('apiClient handles 204 No Content smoothly', async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = (async () => {
    return new Response(null, { status: 204 });
  }) as any;

  try {
    const result = await apiClient('/lifestyle/dealbreakers/123', { method: 'DELETE' });
    assert.strictEqual(result, null);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('apiClient turns a bare "Failed to fetch" into a readable NetworkError (not an ApiError)', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async () => {
    throw new TypeError('Failed to fetch');
  }) as typeof fetch;
  try {
    await assert.rejects(apiClient('/groups'), (err: unknown) => {
      assert.ok(err instanceof NetworkError);
      assert.ok(!(err instanceof ApiError));
      assert.match((err as Error).message, /Can't reach Flatmate/);
      return true;
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('apiClient passes a caller abort straight through', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (_url: string | URL | Request, init?: RequestInit) => {
    throw init?.signal?.reason ?? new Error('aborted');
  }) as typeof fetch;
  const controller = new AbortController();
  controller.abort(new Error('caller cancelled'));
  try {
    await assert.rejects(apiClient('/groups', { signal: controller.signal }), (err: unknown) => {
      assert.ok(!(err instanceof NetworkError));
      return true;
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

test('concurrent 401s share one token refresh and both requests are replayed', async () => {
  const originalFetch = globalThis.fetch;
  mockStorage.setItem('flatmate_access_token', 'old');
  mockStorage.setItem('flatmate_refresh_token', 'r1');
  let refreshCalls = 0;
  globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
    const u = String(url);
    if (u.endsWith('/auth/refresh')) {
      refreshCalls++;
      await new Promise((r) => setTimeout(r, 10));
      return jsonResponse(200, { access_token: 'new', refresh_token: 'r2' });
    }
    const auth = (init?.headers as Record<string, string>)?.Authorization;
    return auth === 'Bearer new' ? jsonResponse(200, { ok: u }) : jsonResponse(401, { detail: 'expired' });
  }) as typeof fetch;
  try {
    const [a, b] = await Promise.all([apiClient<{ ok: string }>('/a'), apiClient<{ ok: string }>('/b')]);
    assert.ok(a.ok.endsWith('/a') && b.ok.endsWith('/b'));
    assert.strictEqual(refreshCalls, 1);
    assert.strictEqual(mockStorage.getItem('flatmate_refresh_token'), 'r2');
  } finally {
    globalThis.fetch = originalFetch;
    mockStorage.clear();
  }
});

test('a network failure while refreshing keeps the session', async () => {
  const originalFetch = globalThis.fetch;
  mockStorage.setItem('flatmate_access_token', 'old');
  mockStorage.setItem('flatmate_refresh_token', 'r1');
  globalThis.fetch = (async () => {
    throw new TypeError('Failed to fetch');
  }) as typeof fetch;
  try {
    await assert.rejects(refreshAccessToken(), NetworkError);
    assert.strictEqual(mockStorage.getItem('flatmate_refresh_token'), 'r1');
  } finally {
    globalThis.fetch = originalFetch;
    mockStorage.clear();
  }
});

test('a rejected refresh token clears the session and announces it', async () => {
  const originalFetch = globalThis.fetch;
  const events: string[] = [];
  (globalThis as any).window.dispatchEvent = (e: { type: string }) => { events.push(e.type); return true; };
  mockStorage.setItem('flatmate_access_token', 'old');
  mockStorage.setItem('flatmate_refresh_token', 'revoked');
  globalThis.fetch = (async () => jsonResponse(401, { detail: 'invalid' })) as typeof fetch;
  try {
    assert.strictEqual(await refreshAccessToken(), null);
    assert.strictEqual(mockStorage.getItem('flatmate_access_token'), null);
    assert.deepStrictEqual(events, ['flatmate:auth-expired']);
  } finally {
    globalThis.fetch = originalFetch;
    (globalThis as any).window.dispatchEvent = () => true;
    mockStorage.clear();
  }
});
