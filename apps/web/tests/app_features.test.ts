import test from 'node:test';
import assert from 'node:assert';
import { FEATURES_IF_UNKNOWN, featuresFrom } from '../lib/app-features-model.ts';

test('features the API turned off are off', () => {
  assert.deepStrictEqual(
    featuresFrom({ api_version: 'v1', features: { phone_verification: false, payments: false } }),
    { phone_verification: false, payments: false },
  );
});

test('an older API without features means everything is on', () => {
  assert.deepStrictEqual(featuresFrom({ api_version: 'v1' }), FEATURES_IF_UNKNOWN);
});

test('only an explicit false turns a feature off', () => {
  assert.deepStrictEqual(
    featuresFrom({ features: { phone_verification: 'no', payments: null } }),
    { phone_verification: true, payments: true },
  );
  assert.deepStrictEqual(featuresFrom(null), FEATURES_IF_UNKNOWN);
  assert.deepStrictEqual(featuresFrom({ features: 'broken' }), FEATURES_IF_UNKNOWN);
});
