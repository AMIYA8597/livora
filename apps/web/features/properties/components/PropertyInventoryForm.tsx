"use client";

import React, { useState } from 'react';

export interface PropertyInventoryFormProps {
  onSubmit: (propertyData: any) => Promise<void>;
  isLoading?: boolean;
}

export const PropertyInventoryForm: React.FC<PropertyInventoryFormProps> = ({
  onSubmit,
  isLoading = false,
}) => {
  const [configuration, setConfiguration] = useState('2BHK');
  const [propertyCategory, setPropertyCategory] = useState('apartment');
  const [monthlyRent, setMonthlyRent] = useState('35000');
  const [securityDeposit, setSecurityDeposit] = useState('100000');
  const [maintenanceMonthly, setMaintenanceMonthly] = useState('2500');
  const [maxCapacity, setMaxCapacity] = useState('2');
  const [addressDisplay, setAddressDisplay] = useState('Koramangala 4th Block, Bengaluru');
  const [addressExact, setAddressExact] = useState('Flat 302, Green Glen Apartments, 4th Cross');
  const [city, setCity] = useState('Bengaluru');
  const [postalCode, setPostalCode] = useState('560034');
  const [foodPolicy, setFoodPolicy] = useState('pure_veg');
  const [smokingPolicy, setSmokingPolicy] = useState('never');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSubmit({
      configuration,
      property_category: propertyCategory,
      monthly_rent: parseFloat(monthlyRent),
      security_deposit: parseFloat(securityDeposit),
      maintenance_monthly: parseFloat(maintenanceMonthly),
      max_capacity: parseInt(maxCapacity, 10),
      current_occupants: 0,
      address_display: addressDisplay,
      address_exact: addressExact,
      city,
      postal_code: postalCode,
      currency: 'INR',
      diet_preference: foodPolicy,
      smoking_allowed: smokingPolicy === 'permitted',
      available_from: new Date().toISOString().split('T')[0],
    });
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm space-y-6">
      <div>
        <h3 className="text-lg font-bold text-gray-900">List Your Accommodation</h3>
        <p className="text-xs text-gray-500">
          Indian rental inventory management: Units, Rooms, Beds, and Lifestyle Policies.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Accommodation Category */}
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">Accommodation Category</label>
          <select
            value={propertyCategory}
            onChange={(e) => setPropertyCategory(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded-lg p-2.5 bg-gray-50 focus:bg-white"
          >
            <option value="apartment">Entire Apartment / Flat</option>
            <option value="independent_house">Independent House / Villa</option>
            <option value="pg">PG (Paying Guest)</option>
            <option value="co_living">Co-Living Space</option>
            <option value="hostel">Hostel Accommodation</option>
          </select>
        </div>

        {/* Configuration */}
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">Unit Configuration</label>
          <select
            value={configuration}
            onChange={(e) => setConfiguration(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded-lg p-2.5 bg-gray-50 focus:bg-white"
          >
            <option value="1RK">1RK (Room Kitchen)</option>
            <option value="1BHK">1BHK</option>
            <option value="2RK">2RK</option>
            <option value="2BHK">2BHK</option>
            <option value="3BHK">3BHK</option>
            <option value="4BHK_plus">4BHK and Above</option>
            <option value="studio">Studio Apartment</option>
          </select>
        </div>

        {/* Financials in INR */}
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">Monthly Rent (₹ INR)</label>
          <input
            type="number"
            value={monthlyRent}
            onChange={(e) => setMonthlyRent(e.target.value)}
            required
            className="w-full text-sm border border-gray-300 rounded-lg p-2.5 focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">Security Deposit (₹ INR)</label>
          <input
            type="number"
            value={securityDeposit}
            onChange={(e) => setSecurityDeposit(e.target.value)}
            required
            className="w-full text-sm border border-gray-300 rounded-lg p-2.5 focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">Maintenance Charges (₹/mo)</label>
          <input
            type="number"
            value={maintenanceMonthly}
            onChange={(e) => setMaintenanceMonthly(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded-lg p-2.5 focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">Max Occupants Capacity</label>
          <input
            type="number"
            min="1"
            max="20"
            value={maxCapacity}
            onChange={(e) => setMaxCapacity(e.target.value)}
            required
            className="w-full text-sm border border-gray-300 rounded-lg p-2.5 focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      {/* Address & Locality */}
      <div className="space-y-3 pt-2 border-t border-gray-100">
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">
            Display Address (Public / Fuzzed to ~1km for Privacy)
          </label>
          <input
            type="text"
            value={addressDisplay}
            onChange={(e) => setAddressDisplay(e.target.value)}
            required
            className="w-full text-sm border border-gray-300 rounded-lg p-2.5"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">
            Exact Flat & Building Address (Masked until confirmed viewing)
          </label>
          <input
            type="text"
            value={addressExact}
            onChange={(e) => setAddressExact(e.target.value)}
            required
            className="w-full text-sm border border-gray-300 rounded-lg p-2.5"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">City</label>
            <input
              type="text"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              required
              className="w-full text-sm border border-gray-300 rounded-lg p-2.5"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">Pincode</label>
            <input
              type="text"
              value={postalCode}
              onChange={(e) => setPostalCode(e.target.value)}
              required
              className="w-full text-sm border border-gray-300 rounded-lg p-2.5"
            />
          </div>
        </div>
      </div>

      {/* Lifestyle Rules */}
      <div className="grid grid-cols-2 gap-4 pt-2 border-t border-gray-100">
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">Diet / Kitchen Restriction</label>
          <select
            value={foodPolicy}
            onChange={(e) => setFoodPolicy(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded-lg p-2.5"
          >
            <option value="pure_veg">Strictly Pure Vegetarian Kitchen</option>
            <option value="veg_and_egg">Vegetarian + Eggs OK</option>
            <option value="non_veg_ok">Non-Vegetarian Cooking Allowed</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">Smoking Policy</label>
          <select
            value={smokingPolicy}
            onChange={(e) => setSmokingPolicy(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded-lg p-2.5"
          >
            <option value="never">Strictly Smoke-Free Household</option>
            <option value="balcony_only">Balcony Only</option>
            <option value="permitted">Smoking Permitted</option>
          </select>
        </div>
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-lg transition-colors shadow"
      >
        {isLoading ? 'Creating Property Inventory...' : 'Publish Listing'}
      </button>
    </form>
  );
};
