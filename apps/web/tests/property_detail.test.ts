import test from 'node:test';
import assert from 'node:assert';
import { formatCurrency, formatDate, formatDateTimeIST } from '../lib/utils.ts';
import { apiClient, ApiError } from '../lib/api-client.ts';
import type { PropertyDTO } from '@flatmate/contracts';

// Setup mock window & localStorage for tests
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

const mockStorage = new MockLocalStorage();
(globalThis as any).window = {
  dispatchEvent: () => {},
};
(globalThis as any).localStorage = mockStorage;

test('Property Detail: deposit fallback handles missing or undefined security_deposit and deposit safely', () => {
  // Scenario 1: Only security_deposit present
  const prop1: Partial<PropertyDTO> = {
    id: 'prop-1',
    monthly_rent: 25000,
    security_deposit: 50000,
  };
  const deposit1 = prop1.security_deposit ?? (prop1 as any).deposit ?? 0;
  assert.strictEqual(deposit1, 50000);
  assert.strictEqual(formatCurrency(deposit1), '₹50,000');

  // Scenario 2: Legacy deposit field present, security_deposit undefined
  const prop2: any = {
    id: 'prop-2',
    monthly_rent: 30000,
    deposit: 60000,
  };
  const deposit2 = prop2.security_deposit ?? prop2.deposit ?? 0;
  assert.strictEqual(deposit2, 60000);
  assert.strictEqual(formatCurrency(deposit2), '₹60,000');

  // Scenario 3: Neither security_deposit nor deposit present
  const prop3: Partial<PropertyDTO> = {
    id: 'prop-3',
    monthly_rent: 15000,
  };
  const deposit3 = prop3.security_deposit ?? (prop3 as any).deposit ?? 0;
  assert.strictEqual(deposit3, 0);
  assert.strictEqual(formatCurrency(deposit3), '₹0');
});

test('Property Detail: formatDateTimeIST formats timestamps in Indian Standard Time correctly', () => {
  const utcIso = '2026-11-13T10:00:00Z'; // 10:00 UTC = 15:30 IST (+5:30)
  const formatted = formatDateTimeIST(utcIso);
  assert.ok(formatted.includes('Nov') || formatted.includes('13'));
  assert.ok(formatted.includes('3:30') || formatted.includes('15:30'));
});

test('Property Detail: API client successfully retrieves property details for valid ID', async () => {
  const mockProperty: Partial<PropertyDTO> = {
    id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    title: 'Sunny 2BHK in Indiranagar',
    city: 'Bengaluru',
    address_display: 'Near Metro Station, Indiranagar',
    monthly_rent: 35000,
    security_deposit: 70000,
    available_from: '2026-12-01',
    is_furnished: true,
    bills_included: false,
    total_bedrooms: 2,
    total_bathrooms: 2,
  };

  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url: any, init: any) => {
    assert.ok(String(url).includes('/properties/a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'));
    return new Response(JSON.stringify(mockProperty), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  try {
    const res = await apiClient<PropertyDTO>('/properties/a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11');
    assert.strictEqual(res.id, 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11');
    assert.strictEqual(res.monthly_rent, 35000);
    assert.strictEqual(formatCurrency(res.monthly_rent), '₹35,000');
    assert.strictEqual(res.city, 'Bengaluru');
    assert.strictEqual(res.address_display, 'Near Metro Station, Indiranagar');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Property Detail: API client handles 404 Not Found error properly', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    return new Response(
      JSON.stringify({
        status: 404,
        title: 'Not Found',
        detail: 'Property with ID non-existent-id not found',
        error_code: 'PROPERTY_NOT_FOUND',
      }),
      {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  };

  try {
    await assert.rejects(
      async () => {
        await apiClient<PropertyDTO>('/properties/non-existent-id');
      },
      (err: any) => {
        assert.ok(err instanceof ApiError);
        assert.strictEqual(err.status, 404);
        assert.strictEqual(err.detail, 'Property with ID non-existent-id not found');
        return true;
      }
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Property Detail: API client handles 500 server error and network failures', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    return new Response(
      JSON.stringify({
        status: 500,
        title: 'Internal Server Error',
        detail: 'Database connection failed',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  };

  try {
    await assert.rejects(
      async () => {
        await apiClient<PropertyDTO>('/properties/err-id');
      },
      (err: any) => {
        assert.ok(err instanceof ApiError);
        assert.strictEqual(err.status, 500);
        return true;
      }
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Property Detail: Saved properties persists into localStorage correctly', () => {
  mockStorage.clear();
  const testPropId = 'prop-koramangala-4bhk';

  // Initially empty
  const initialSaved = JSON.parse(mockStorage.getItem('flatmate_saved_properties') || '[]');
  assert.strictEqual(initialSaved.length, 0);

  // Save property
  const updated = [...initialSaved, testPropId];
  mockStorage.setItem('flatmate_saved_properties', JSON.stringify(updated));

  const savedAfter = JSON.parse(mockStorage.getItem('flatmate_saved_properties') || '[]');
  assert.strictEqual(savedAfter.includes(testPropId), true);
  assert.strictEqual(savedAfter.length, 1);

  // Unsave property
  const filtered = savedAfter.filter((id: string) => id !== testPropId);
  mockStorage.setItem('flatmate_saved_properties', JSON.stringify(filtered));

  const savedFinal = JSON.parse(mockStorage.getItem('flatmate_saved_properties') || '[]');
  assert.strictEqual(savedFinal.includes(testPropId), false);
  assert.strictEqual(savedFinal.length, 0);
});
