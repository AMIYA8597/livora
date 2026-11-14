"use client";

import React, { useState } from "react";
import { Plus, Trash2, Bed, Home, AlertCircle, CheckCircle2 } from "lucide-react";
import { Button, Input } from "@flatmate/ui";
import { formatCurrency } from "@/lib/utils";

export interface BedConfig {
  id: string;
  bed_identifier: string;
  bed_type: string;
  rent_per_bed: number;
  is_available: boolean;
}

export interface RoomConfig {
  id: string;
  room_name: string;
  room_type: "private" | "shared";
  capacity: number;
  room_rent: number;
  deposit: number;
  private_bath: boolean;
  beds: BedConfig[];
}

export interface PropertyInventoryFormProps {
  initialData?: any;
  onSubmit: (propertyData: any) => Promise<void>;
  isLoading?: boolean;
}

export const PropertyInventoryForm: React.FC<PropertyInventoryFormProps> = ({
  initialData,
  onSubmit,
  isLoading = false,
}) => {
  const [configuration, setConfiguration] = useState(initialData?.configuration || "2BHK");
  const [propertyCategory, setPropertyCategory] = useState(initialData?.property_category || "apartment");
  const [monthlyRent, setMonthlyRent] = useState(String(initialData?.monthly_rent || "35000"));
  const [securityDeposit, setSecurityDeposit] = useState(String(initialData?.security_deposit || "100000"));
  const [maintenanceMonthly, setMaintenanceMonthly] = useState(String(initialData?.maintenance_monthly || "2500"));
  const [maxCapacity, setMaxCapacity] = useState(String(initialData?.max_capacity || "4"));
  const [addressDisplay, setAddressDisplay] = useState(initialData?.address_display || "Koramangala 4th Block, Bengaluru");
  const [addressExact, setAddressExact] = useState(initialData?.address_exact || "Flat 302, Green Glen Apartments, 4th Cross");
  const [city, setCity] = useState(initialData?.city || "Bengaluru");
  const [postalCode, setPostalCode] = useState(initialData?.postal_code || "560034");
  const [foodPolicy, setFoodPolicy] = useState(initialData?.diet_preference || "pure_veg");
  const [smokingPolicy, setSmokingPolicy] = useState(initialData?.smoking_allowed ? "permitted" : "never");

  // Hierarchical Room & Bed Inventory
  const [rooms, setRooms] = useState<RoomConfig[]>(
    initialData?.rooms || [
      {
        id: "room-1",
        room_name: "Master Bedroom",
        room_type: "private",
        capacity: 1,
        room_rent: 18000,
        deposit: 50000,
        private_bath: true,
        beds: [
          {
            id: "bed-1",
            bed_identifier: "Bed A (King Size)",
            bed_type: "double",
            rent_per_bed: 18000,
            is_available: true,
          },
        ],
      },
      {
        id: "room-2",
        room_name: "Guest Bedroom",
        room_type: "shared",
        capacity: 2,
        room_rent: 17000,
        deposit: 50000,
        private_bath: false,
        beds: [
          {
            id: "bed-2",
            bed_identifier: "Bed A (Window Side)",
            bed_type: "single",
            rent_per_bed: 8500,
            is_available: true,
          },
          {
            id: "bed-3",
            bed_identifier: "Bed B",
            bed_type: "single",
            rent_per_bed: 8500,
            is_available: true,
          },
        ],
      },
    ]
  );

  const [validationError, setValidationError] = useState<string | null>(null);

  // Add Room
  const handleAddRoom = () => {
    const nextIdx = rooms.length + 1;
    setRooms([
      ...rooms,
      {
        id: `room-${Date.now()}`,
        room_name: `Bedroom ${nextIdx}`,
        room_type: "private",
        capacity: 1,
        room_rent: 15000,
        deposit: 45000,
        private_bath: false,
        beds: [
          {
            id: `bed-${Date.now()}`,
            bed_identifier: "Bed A",
            bed_type: "single",
            rent_per_bed: 15000,
            is_available: true,
          },
        ],
      },
    ]);
  };

  const handleRemoveRoom = (roomId: string) => {
    if (rooms.length <= 1) return;
    setRooms(rooms.filter((r) => r.id !== roomId));
  };

  // Add Bed to Room
  const handleAddBed = (roomId: string) => {
    setRooms(
      rooms.map((r) => {
        if (r.id !== roomId) return r;
        const letter = String.fromCharCode(65 + r.beds.length);
        const newBedRent = Math.round(r.room_rent / (r.beds.length + 1));
        return {
          ...r,
          capacity: r.capacity + 1,
          beds: [
            ...r.beds,
            {
              id: `bed-${Date.now()}`,
              bed_identifier: `Bed ${letter}`,
              bed_type: "single",
              rent_per_bed: newBedRent,
              is_available: true,
            },
          ],
        };
      })
    );
  };

  const handleRemoveBed = (roomId: string, bedId: string) => {
    setRooms(
      rooms.map((r) => {
        if (r.id !== roomId || r.beds.length <= 1) return r;
        return {
          ...r,
          capacity: Math.max(1, r.capacity - 1),
          beds: r.beds.filter((b) => b.id !== bedId),
        };
      })
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    // Validate capacity conflict: Total room capacity must not exceed Property Max Capacity
    const totalRoomCapacity = rooms.reduce((sum, r) => sum + r.capacity, 0);
    const parsedMaxCapacity = parseInt(maxCapacity, 10);
    if (totalRoomCapacity > parsedMaxCapacity) {
      setValidationError(
        `Capacity conflict: Sum of room capacities (${totalRoomCapacity}) exceeds property max capacity (${parsedMaxCapacity}). Please adjust room capacity or property maximum.`
      );
      return;
    }

    // Validate bed count per room
    for (const r of rooms) {
      if (r.beds.length === 0) {
        setValidationError(`Room "${r.room_name}" must have at least one bed configured.`);
        return;
      }
    }

    await onSubmit({
      configuration,
      property_category: propertyCategory,
      monthly_rent: parseFloat(monthlyRent),
      security_deposit: parseFloat(securityDeposit),
      maintenance_monthly: parseFloat(maintenanceMonthly),
      max_capacity: parsedMaxCapacity,
      current_occupants: 0,
      address_display: addressDisplay,
      address_exact: addressExact,
      city,
      postal_code: postalCode,
      currency: "INR",
      diet_preference: foodPolicy,
      smoking_allowed: smokingPolicy === "permitted",
      available_from: new Date().toISOString().split("T")[0],
      rooms: rooms.map((r) => ({
        room_name: r.room_name,
        room_type: r.room_type,
        capacity: r.capacity,
        room_rent: r.room_rent,
        deposit: r.deposit,
        private_bath: r.private_bath,
        beds: r.beds.map((b) => ({
          bed_identifier: b.bed_identifier,
          bed_type: b.bed_type,
          rent_per_bed: b.rent_per_bed,
          is_available: b.is_available,
        })),
      })),
    });
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-xs space-y-6">
      <div>
        <h3 className="text-lg font-extrabold text-slate-900">Property Inventory Architecture</h3>
        <p className="text-xs text-slate-500 mt-0.5">
          Indian rental inventory hierarchy: Property Units → Rooms → Beds with capacity conflict validation.
        </p>
      </div>

      {validationError && (
        <div className="flex items-center space-x-2 p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{validationError}</span>
        </div>
      )}

      {/* Basic Configuration */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">Accommodation Category</label>
          <select
            value={propertyCategory}
            onChange={(e) => setPropertyCategory(e.target.value)}
            className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
          >
            <option value="apartment">Entire Apartment / Flat</option>
            <option value="independent_house">Independent House / Villa</option>
            <option value="pg">PG (Paying Guest)</option>
            <option value="co_living">Co-Living Space</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">Unit Configuration</label>
          <select
            value={configuration}
            onChange={(e) => setConfiguration(e.target.value)}
            className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
          >
            <option value="1RK">1RK</option>
            <option value="1BHK">1BHK</option>
            <option value="2RK">2RK</option>
            <option value="2BHK">2BHK</option>
            <option value="3BHK">3BHK</option>
            <option value="4BHK_plus">4BHK+</option>
            <option value="studio">Studio</option>
          </select>
        </div>

        <Input
          label="Total Monthly Rent (₹ INR)"
          type="number"
          required
          value={monthlyRent}
          onChange={(e) => setMonthlyRent(e.target.value)}
        />

        <Input
          label="Security Deposit (₹ INR)"
          type="number"
          required
          value={securityDeposit}
          onChange={(e) => setSecurityDeposit(e.target.value)}
        />

        <Input
          label="Maintenance Charges (₹/mo)"
          type="number"
          value={maintenanceMonthly}
          onChange={(e) => setMaintenanceMonthly(e.target.value)}
        />

        <Input
          label="Property Max Capacity (Persons)"
          type="number"
          min="1"
          required
          value={maxCapacity}
          onChange={(e) => setMaxCapacity(e.target.value)}
        />
      </div>

      {/* Address & Locality */}
      <div className="space-y-3 pt-3 border-t border-slate-100">
        <Input
          label="Display Locality (Public / Fuzzed for Privacy)"
          required
          value={addressDisplay}
          onChange={(e) => setAddressDisplay(e.target.value)}
        />

        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">
            Exact Building & Flat Address (Masked until confirmed viewing)
          </label>
          <input
            type="text"
            required
            value={addressExact}
            onChange={(e) => setAddressExact(e.target.value)}
            className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Input label="City" required value={city} onChange={(e) => setCity(e.target.value)} />
          <Input label="Postal Code" required value={postalCode} onChange={(e) => setPostalCode(e.target.value)} />
        </div>
      </div>

      {/* Room and Bed Hierarchy Management */}
      <div className="space-y-4 pt-3 border-t border-slate-100">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="font-bold text-slate-900 text-sm">Room & Bed Inventory Hierarchy</h4>
            <span className="text-xs text-slate-400">
              Configure room-level privacy, rent share, and individual bed slots.
            </span>
          </div>
          <Button type="button" size="sm" variant="outline" className="gap-1.5" onClick={handleAddRoom}>
            <Plus className="w-3.5 h-3.5" />
            <span>Add Room</span>
          </Button>
        </div>

        <div className="space-y-4">
          {rooms.map((room, rIdx) => (
            <div key={room.id} className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Home className="w-4 h-4 text-indigo-600" />
                  <span className="font-bold text-slate-800 text-sm">Room {rIdx + 1}</span>
                </div>
                {rooms.length > 1 && (
                  <button
                    type="button"
                    onClick={() => handleRemoveRoom(room.id)}
                    className="text-xs text-rose-500 hover:text-rose-700 flex items-center gap-1"
                  >
                    <Trash2 className="w-3.5 h-3.5" /> Remove Room
                  </button>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <Input
                  label="Room Name"
                  value={room.room_name}
                  onChange={(e) => {
                    const u = [...rooms];
                    u[rIdx].room_name = e.target.value;
                    setRooms(u);
                  }}
                />
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Room Type</label>
                  <select
                    value={room.room_type}
                    onChange={(e) => {
                      const u = [...rooms];
                      u[rIdx].room_type = e.target.value as "private" | "shared";
                      setRooms(u);
                    }}
                    className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
                  >
                    <option value="private">Private En-Suite</option>
                    <option value="shared">Shared Room</option>
                  </select>
                </div>
                <Input
                  label="Room Rent (₹/mo)"
                  type="number"
                  value={String(room.room_rent)}
                  onChange={(e) => {
                    const u = [...rooms];
                    u[rIdx].room_rent = parseFloat(e.target.value) || 0;
                    setRooms(u);
                  }}
                />
              </div>

              {/* Beds under Room */}
              <div className="space-y-2 pt-2 border-t border-slate-200">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-600">Beds in this Room:</span>
                  <button
                    type="button"
                    onClick={() => handleAddBed(room.id)}
                    className="text-xs text-indigo-600 font-bold hover:underline"
                  >
                    + Add Bed Slot
                  </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {room.beds.map((b) => (
                    <div
                      key={b.id}
                      className="p-2.5 bg-white border border-slate-200/80 rounded-xl flex items-center justify-between text-xs"
                    >
                      <div className="flex items-center space-x-2">
                        <Bed className="w-3.5 h-3.5 text-slate-400" />
                        <div>
                          <span className="font-semibold text-slate-800">{b.bed_identifier}</span>
                          <span className="text-[10px] text-slate-400 block">
                            {formatCurrency(b.rent_per_bed, "INR")}/mo
                          </span>
                        </div>
                      </div>

                      {room.beds.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveBed(room.id, b.id)}
                          className="text-rose-500 p-1"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <Button
        type="submit"
        variant="primary"
        size="md"
        disabled={isLoading}
        className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 shadow-md"
      >
        {isLoading ? "Persisting Inventory..." : "Publish Inventory Hierarchy"}
      </Button>
    </form>
  );
};
