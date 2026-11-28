import test from 'node:test';
import assert from 'node:assert';
import { apiClient, ApiError, NetworkError, API_BASE_URL, refreshAccessToken, busyRetryDelayMs, BUSY_RETRIES } from '../lib/api-client.ts';

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


test('busy 503s are retried after Retry-After, with jitter, a limited number of times', () => {
  const half = () => 0.5;
  // Refused before any work: every method may retry.
  assert.strictEqual(busyRetryDelayMs('GET', 503, 'SERVER_BUSY', '2', 0, half), 2000);
  assert.strictEqual(busyRetryDelayMs('POST', 503, 'SERVER_BUSY', '3', 1, half), 3000);
  // Database busy: reads only (a write may have got partway).
  assert.strictEqual(busyRetryDelayMs('GET', 503, 'SERVICE_BUSY', '2', 0, half), 2000);
  assert.strictEqual(busyRetryDelayMs('POST', 503, 'SERVICE_BUSY', '2', 0, half), null);
  // Jitter spreads the wait between 0.5x and 1.5x; long waits are capped.
  assert.strictEqual(busyRetryDelayMs('GET', 503, 'SERVER_BUSY', '2', 0, () => 0), 1000);
  assert.strictEqual(busyRetryDelayMs('GET', 503, 'SERVER_BUSY', '60', 0, half), 5000);
  // No header: one second.
  assert.strictEqual(busyRetryDelayMs('GET', 503, 'SERVER_BUSY', null, 0, half), 1000);
  // Other errors, and after the last retry, are shown.
  assert.strictEqual(busyRetryDelayMs('GET', 503, 'SERVER_BUSY', '2', BUSY_RETRIES, half), null);
  assert.strictEqual(busyRetryDelayMs('GET', 503, undefined, '2', 0, half), null);
  assert.strictEqual(busyRetryDelayMs('GET', 500, 'SERVER_BUSY', '2', 0, half), null);
  assert.strictEqual(busyRetryDelayMs('GET', 429, 'RATE_LIMITED', '2', 0, half), null);
});

test('apiClient retries a busy 503 and returns the later answer', async () => {
  const originalFetch = globalThis.fetch;
  const originalTimeout = globalThis.setTimeout;
  let calls = 0;
  // Run the retry wait at once.
  (globalThis as any).setTimeout = (fn: () => void, ms?: number) => originalTimeout(fn, ms && ms > 100 ? 0 : ms);
  globalThis.fetch = (async () => {
    calls += 1;
    if (calls === 1) {
      return new Response(JSON.stringify({ status: 503, title: 'Server Busy', error_code: 'SERVER_BUSY' }), {
        status: 503, headers: { 'Content-Type': 'application/problem+json', 'Retry-After': '2' },
      });
    }
    return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  }) as typeof fetch;
  try {
    const body = await apiClient<{ ok: boolean }>('/busy-then-ok');
    assert.deepStrictEqual(body, { ok: true });
    assert.strictEqual(calls, 2);
  } finally {
    globalThis.fetch = originalFetch;
    (globalThis as any).setTimeout = originalTimeout;
  }
});

test('apiClient shows the busy error once the retries are used up', async () => {
  const originalFetch = globalThis.fetch;
  const originalTimeout = globalThis.setTimeout;
  let calls = 0;
  (globalThis as any).setTimeout = (fn: () => void, ms?: number) => originalTimeout(fn, ms && ms > 100 ? 0 : ms);
  globalThis.fetch = (async () => {
    calls += 1;
    return new Response(JSON.stringify({ status: 503, title: 'Server Busy', error_code: 'SERVER_BUSY', detail: 'Busy' }), {
      status: 503, headers: { 'Content-Type': 'application/problem+json', 'Retry-After': '2' },
    });
  }) as typeof fetch;
  try {
    await assert.rejects(apiClient('/always-busy'), (err: unknown) => err instanceof ApiError && err.status === 503);
    assert.strictEqual(calls, 1 + BUSY_RETRIES);
  } finally {
    globalThis.fetch = originalFetch;
    (globalThis as any).setTimeout = originalTimeout;
  }
});

test('a validation error reads as a sentence, never "[object Object]"', () => {
  const fastapi422 = [{ type: 'uuid_parsing', loc: ['path', 'property_id'], msg: 'Input should be a valid UUID' }];
  assert.strictEqual(new ApiError({ status: 422, detail: fastapi422 }).message, 'Input should be a valid UUID');
  assert.strictEqual(
    new ApiError({ status: 422, detail: [{ msg: "Value error, Move-in date can't be in the past" }] }).message,
    "Move-in date can't be in the past",
  );
  assert.strictEqual(new ApiError({ status: 422, detail: [{ odd: true }] }).message, "Some of the details sent weren't valid.");
  assert.strictEqual(new ApiError({ status: 400, detail: { message: 'Nope' } }).message, 'Nope');
  assert.strictEqual(new ApiError({ status: 500, detail: {}, title: 'Server Error' }).message, 'Server Error');
  assert.strictEqual(new ApiError({ status: 409, detail: 'Already applied' }).message, 'Already applied');
});
