import test from 'node:test';
import assert from 'node:assert';
import { formatCurrency } from '../lib/utils.ts';

test('formatCurrency correctly formats Indian Rupee (INR) amounts and grouping', () => {
  // Expected examples from Phase 17.2 spec:
  // ₹500, ₹5,000, ₹50,000, ₹1,00,000, ₹10,00,000
  assert.strictEqual(formatCurrency(500), '₹500');
  assert.strictEqual(formatCurrency(5000), '₹5,000');
  assert.strictEqual(formatCurrency(50000), '₹50,000');
  assert.strictEqual(formatCurrency(100000), '₹1,00,000');
  assert.strictEqual(formatCurrency(1000000), '₹10,00,000');
});

test('formatCurrency handles decimal amounts without silent loss', () => {
  // Fractional amounts should show 2 decimals
  const result1 = formatCurrency(50000.5);
  assert.strictEqual(result1, '₹50,000.50');

  const result2 = formatCurrency(1250.75);
  assert.strictEqual(result2, '₹1,250.75');

  // Whole numbers should not have redundant .00 by default
  const result3 = formatCurrency(25000);
  assert.strictEqual(result3, '₹25,000');
});

test('formatCurrency correctly formats zero and negative amounts', () => {
  assert.strictEqual(formatCurrency(0), '₹0');
  assert.strictEqual(formatCurrency(-500), '-₹500');
  assert.strictEqual(formatCurrency(-50000), '-₹50,000');
});

test('formatCurrency parses valid numeric strings where contract permits', () => {
  assert.strictEqual(formatCurrency('35000'), '₹35,000');
  assert.strictEqual(formatCurrency(' 75000 '), '₹75,000');
  assert.strictEqual(formatCurrency('12500.50'), '₹12,500.50');
});

test('formatCurrency does NOT silently convert invalid or missing values into ₹0', () => {
  // Missing values return "N/A"
  assert.strictEqual(formatCurrency(null), 'N/A');
  assert.strictEqual(formatCurrency(undefined), 'N/A');

  // Invalid strings return "N/A"
  assert.strictEqual(formatCurrency('invalid_number'), 'N/A');
  assert.strictEqual(formatCurrency(''), 'N/A');
  assert.strictEqual(formatCurrency(NaN), 'N/A');

  // Custom fallback option
  assert.strictEqual(formatCurrency(null, { fallback: '—' }), '—');
  assert.strictEqual(formatCurrency('bad', { fallback: 'Invalid' }), 'Invalid');
});

test('formatCurrency supports other currencies such as USD', () => {
  const usdResult = formatCurrency(4200, 'USD');
  assert.strictEqual(usdResult, '$4,200');

  const usdDecimal = formatCurrency(4200.75, 'USD');
  assert.strictEqual(usdDecimal, '$4,200.75');
});
