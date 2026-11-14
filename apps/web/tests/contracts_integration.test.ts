import test from 'node:test';
import assert from 'node:assert';
import {
  formatCurrency,
  formatIndianCompactCurrency,
  formatDate,
  formatDateTimeIST,
  formatIndianPhoneNumber,
  TOP_INDIAN_CITIES,
} from '../lib/utils.ts';
import type {
  PropertyDTO,
  ScoreBreakdown,
  GroupDTO,
  ApplicationDTO,
  AppointmentDTO,
  OwnerDashboardStatsDTO,
  ExistingTenantVacancyDTO,
  PGBuildingDTO,
  UserTrustStatusDTO,
} from '@flatmate/contracts';

test('formatCurrency formats INR by default and respects currency parameter', () => {
  const inrResult = formatCurrency(35000);
  assert.ok(inrResult.includes('35,000'));

  const usdResult = formatCurrency(4200, 'USD');
  assert.ok(usdResult.includes('$4,200') || usdResult.includes('4,200'));

  const zeroResult = formatCurrency(0);
  assert.ok(zeroResult.includes('0'));

  const nullResult = formatCurrency(null);
  assert.strictEqual(nullResult, 'N/A');
});

test('formatIndianCompactCurrency handles Lakhs, Crores, and Thousands', () => {
  assert.strictEqual(formatIndianCompactCurrency(15000000), '₹1.5 Cr');
  assert.strictEqual(formatIndianCompactCurrency(350000), '₹3.5 L');
  assert.strictEqual(formatIndianCompactCurrency(25000), '₹25 k');
  assert.strictEqual(formatIndianCompactCurrency(800), '₹800');
  assert.strictEqual(formatIndianCompactCurrency(null), '₹0');
});

test('formatDate safely formats valid dates and falls back for empty', () => {
  const formatted = formatDate('2026-11-25');
  assert.ok(formatted.includes('Nov') || formatted.includes('25'));

  assert.strictEqual(formatDate(null), 'Flexible');
  assert.strictEqual(formatDate(undefined), 'Flexible');
});

test('formatDateTimeIST outputs date and time in Indian Standard Time', () => {
  const formatted = formatDateTimeIST('2026-11-25T14:30:00Z');
  assert.ok(formatted.includes('Nov') || formatted.includes('25'));
  assert.strictEqual(formatDateTimeIST(null), 'Flexible');
});

test('formatIndianPhoneNumber formats and masks numbers correctly', () => {
  const unmasked = formatIndianPhoneNumber('+919876543210');
  assert.strictEqual(unmasked, '+91 98765 43210');

  const tenDigit = formatIndianPhoneNumber('9876543210');
  assert.strictEqual(tenDigit, '+91 98765 43210');

  const masked = formatIndianPhoneNumber('+919876543210', true);
  assert.strictEqual(masked, '+91 XXXXX XX3210');

  assert.strictEqual(formatIndianPhoneNumber(null), 'Not provided');
});

test('TOP_INDIAN_CITIES provides comprehensive Indian metros and localities', () => {
  assert.ok(TOP_INDIAN_CITIES.length >= 6);
  const bengaluru = TOP_INDIAN_CITIES.find((c) => c.name === 'Bengaluru');
  assert.ok(bengaluru);
  assert.ok(bengaluru.localities.includes('Koramangala'));
  assert.ok(bengaluru.localities.includes('HSR Layout'));
});

test('PropertyDTO shape conforms to backend schema expectations', () => {
  const sampleProp: PropertyDTO = {
    id: 'prop-uuid-1',
    owner_id: 'owner-uuid-1',
    title: '2BHK Apartment in HSR Layout',
    description: 'Spacious apartment near metro station.',
    property_category: 'apartment',
    configuration: '2BHK',
    latitude: 12.9716,
    longitude: 77.5946,
    address_display: 'HSR Layout Sector 2, Bengaluru',
    address_exact: '[Exact address protected - revealed upon confirmed visit]',
    city: 'Bengaluru',
    postal_code: '560102',
    country: 'India',
    currency: 'INR',
    monthly_rent: 28000,
    security_deposit: 84000,
    maintenance_monthly: 2000,
    bills_included: false,
    total_bedrooms: 2,
    total_bathrooms: 2,
    max_capacity: 4,
    current_occupants: 1,
    available_from: '2026-12-01',
    is_furnished: false,
    furnishing_status: 'semi_furnished',
    pets_allowed: false,
    smoking_allowed: false,
    images: ['https://images.unsplash.com/photo-1?w=800'],
    amenities: ['wifi', 'power_backup', 'lift'],
    rooms: [
      {
        id: 'room-1',
        property_id: 'prop-uuid-1',
        room_name: 'Master Bedroom',
        room_type: 'private',
        room_rent: 15000,
        deposit: 45000,
        private_bath: true,
        is_available: true,
        available_from: '2026-12-01',
        beds: [],
      },
    ],
    is_active: true,
    created_at: '2026-11-01T00:00:00Z',
  };

  assert.strictEqual(sampleProp.currency, 'INR');
  assert.strictEqual(sampleProp.monthly_rent, 28000);
  assert.strictEqual(sampleProp.rooms.length, 1);
  assert.strictEqual(sampleProp.rooms[0].room_rent, 15000);
});

test('ScoreBreakdown supports 10-dimension factors dictionary', () => {
  const sampleScore: ScoreBreakdown = {
    overall_score: 87.5,
    dealbreakers_cleared: true,
    conflicts: [],
    factors: {
      working_schedule: 90,
      sleep_schedule: 95,
      budget: 85,
      cleanliness: 90,
      lifestyle: 80,
      noise_and_lighting: 85,
      guests_and_social: 75,
      food_and_cooking: 90,
      professional_domain: 80,
      location: 100,
    },
    explanations: {
      working_schedule: 'Both share matching work routines.',
      sleep_schedule: 'Harmonious sleep cycles.',
    },
    algorithm_version: 'v1.0-india-heuristic',
    shared_interests: ['Early morning routine', 'Quiet study hours'],
  };

  assert.strictEqual(sampleScore.overall_score, 87.5);
  assert.strictEqual(sampleScore.dealbreakers_cleared, true);
  assert.strictEqual(Object.keys(sampleScore.factors || {}).length, 10);
  assert.strictEqual(sampleScore.factors?.cleanliness, 90);
});

test('GroupDTO supports members and wishlist items', () => {
  const sampleGroup: GroupDTO = {
    id: 'grp-1',
    creator_id: 'user-1',
    name: 'Bangalore Tech Flatshare',
    description: 'Looking for 3BHK flat in Indiranagar',
    target_budget_total: 60000,
    target_city: 'Bengaluru',
    members: [
      {
        id: 'mem-1',
        group_id: 'grp-1',
        user_id: 'user-1',
        role: 'leader',
        joined_at: '2026-11-01T00:00:00Z',
      },
    ],
    wishlist_items: [
      {
        id: 'wish-1',
        group_id: 'grp-1',
        property_id: 'prop-1',
        added_by: 'user-1',
        votes: { 'user-1': 'up' },
        created_at: '2026-11-01T00:00:00Z',
      },
    ],
    created_at: '2026-11-01T00:00:00Z',
  };

  assert.strictEqual(sampleGroup.members.length, 1);
  assert.strictEqual(sampleGroup.target_budget_total, 60000);
});
