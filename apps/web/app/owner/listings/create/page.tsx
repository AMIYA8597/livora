"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api-client";
import { Card, Button, Input, Badge } from "@flatmate/ui";
import { FileUpload } from "@/components/FileUpload";
import { formatCurrency } from "@/lib/utils";
import {
  Building,
  MapPin,
  Home,
  Bed,
  IndianRupee,
  ShieldAlert,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Plus,
  Trash2,
  Sparkles,
} from "lucide-react";

interface RoomItem {
  id: string;
  name: string;
  type: "private" | "shared";
  rent: number;
  deposit: number;
  privateBath: boolean;
  beds: { id: string; identifier: string; rent: number; available: boolean }[];
}

export default function ListingCreationWizardPage() {
  const router = useRouter();
  const { isAuthenticated, isOwner, user } = useAuth();

  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successPropId, setSuccessPropId] = useState<string | null>(null);

  // Step 1: Basic Information
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [propertyCategory, setPropertyCategory] = useState("apartment");

  // Step 2: Location
  const [city, setCity] = useState("Bengaluru");
  const [state, setState] = useState("Karnataka");
  const [locality, setLocality] = useState("Koramangala 4th Block");
  const [addressExact, setAddressExact] = useState("");
  const [postalCode, setPostalCode] = useState("560034");

  // Step 3: Property Configuration
  const [configuration, setConfiguration] = useState("2BHK");
  const [furnishingStatus, setFurnishingStatus] = useState("semi_furnished");
  const [totalBedrooms, setTotalBedrooms] = useState("2");
  const [totalBathrooms, setTotalBathrooms] = useState("2");
  const [maxCapacity, setMaxCapacity] = useState("4");

  // Step 4 & 5: Rooms and Beds
  const [rooms, setRooms] = useState<RoomItem[]>([
    {
      id: "room-1",
      name: "Master Bedroom",
      type: "private",
      rent: 18000,
      deposit: 50000,
      privateBath: true,
      beds: [{ id: "bed-1", identifier: "Bed A", rent: 18000, available: true }],
    },
  ]);

  // Step 6: Financial Information
  const [monthlyRent, setMonthlyRent] = useState("35000");
  const [securityDeposit, setSecurityDeposit] = useState("100000");
  const [maintenanceMonthly, setMaintenanceMonthly] = useState("2500");
  const [billsIncluded, setBillsIncluded] = useState(false);

  // Step 7: Amenities and Rules
  const [amenities, setAmenities] = useState<string[]>([
    "wifi",
    "power_backup",
    "lift",
    "security",
  ]);
  const [kitchenPolicy, setKitchenPolicy] = useState("veg_and_non_veg");
  const [smokingPolicy, setSmokingPolicy] = useState("never");
  const [petsAllowed, setPetsAllowed] = useState(false);

  // Step 8: Images
  const [uploadedImages, setUploadedImages] = useState<string[]>([]);

  // Room Helpers
  const addRoom = () => {
    const newIdx = rooms.length + 1;
    setRooms([
      ...rooms,
      {
        id: `room-${Date.now()}`,
        name: `Bedroom ${newIdx}`,
        type: "private",
        rent: 15000,
        deposit: 45000,
        privateBath: false,
        beds: [{ id: `bed-${Date.now()}`, identifier: "Bed A", rent: 15000, available: true }],
      },
    ]);
  };

  const removeRoom = (roomId: string) => {
    if (rooms.length <= 1) return;
    setRooms(rooms.filter((r) => r.id !== roomId));
  };

  const addBedToRoom = (roomId: string) => {
    setRooms(
      rooms.map((r) => {
        if (r.id !== roomId) return r;
        const newBedLetter = String.fromCharCode(65 + r.beds.length);
        return {
          ...r,
          beds: [
            ...r.beds,
            {
              id: `bed-${Date.now()}`,
              identifier: `Bed ${newBedLetter}`,
              rent: Math.round(r.rent / (r.beds.length + 1)),
              available: true,
            },
          ],
        };
      })
    );
  };

  const removeBedFromRoom = (roomId: string, bedId: string) => {
    setRooms(
      rooms.map((r) => {
        if (r.id !== roomId || r.beds.length <= 1) return r;
        return { ...r, beds: r.beds.filter((b) => b.id !== bedId) };
      })
    );
  };

  const toggleAmenity = (item: string) => {
    setAmenities((prev) =>
      prev.includes(item) ? prev.filter((a) => a !== item) : [...prev, item]
    );
  };

  const handleFinalSubmit = async () => {
    setIsSubmitting(true);
    setError(null);

    try {
      const payload = {
        title: title || `${configuration} in ${locality}, ${city}`,
        description: description || `Verified ${configuration} listing with modern amenities.`,
        property_category: propertyCategory,
        configuration,
        latitude: 12.9716,
        longitude: 77.5946,
        address_display: `${locality}, ${city}`,
        address_exact: addressExact || `${locality}, ${city}`,
        city,
        state,
        postal_code: postalCode,
        country: "India",
        currency: "INR",
        monthly_rent: parseFloat(monthlyRent),
        security_deposit: parseFloat(securityDeposit),
        maintenance_monthly: parseFloat(maintenanceMonthly),
        bills_included: billsIncluded,
        total_bedrooms: parseInt(totalBedrooms, 10),
        total_bathrooms: parseInt(totalBathrooms, 10),
        max_capacity: parseInt(maxCapacity, 10),
        current_occupants: 0,
        available_from: new Date().toISOString().split("T")[0],
        is_furnished: furnishingStatus !== "unfurnished",
        furnishing_status: furnishingStatus,
        pets_allowed: petsAllowed,
        smoking_allowed: smokingPolicy === "permitted",
        images:
          uploadedImages.length > 0
            ? uploadedImages
            : ["https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800"],
        amenities,
      };

      const res = await apiClient<{ id: string }>("/properties", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setSuccessPropId(res.id);
    } catch (err: any) {
      setError(err.message || "Failed to publish listing. Please check required fields.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (successPropId) {
    return (
      <div className="max-w-2xl mx-auto py-16 px-4 text-center space-y-5">
        <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-3xl flex items-center justify-center mx-auto shadow-md shadow-emerald-100">
          <CheckCircle2 className="w-8 h-8" />
        </div>
        <h1 className="text-2xl font-extrabold text-slate-900">Property Published Successfully!</h1>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          Your accommodation inventory has been registered and is now live for verified flatmate seekers to discover.
        </p>
        <div className="flex items-center justify-center space-x-3 pt-4">
          <Link href={`/properties/${successPropId}`}>
            <Button variant="primary" size="md">
              View Public Listing
            </Button>
          </Link>
          <Link href="/owner/dashboard">
            <Button variant="outline" size="md">
              Return to Owner Dashboard
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-10 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <span className="text-xs font-semibold text-indigo-600 uppercase tracking-wider block">
            Step {step} of 9
          </span>
          <h1 className="text-2xl font-extrabold text-slate-900">
            {step === 1 && "Basic Property Information"}
            {step === 2 && "Location & Privacy Masking"}
            {step === 3 && "Unit Configuration & Capacity"}
            {step === 4 && "Room Inventory Configuration"}
            {step === 5 && "Bed Inventory Allocation"}
            {step === 6 && "Financials & Deposit (INR)"}
            {step === 7 && "Amenities & Lifestyle Policies"}
            {step === 8 && "Listing Photography & Uploads"}
            {step === 9 && "Final Review & Publication"}
          </h1>
        </div>
        <Link href="/owner/dashboard" className="text-xs font-semibold text-slate-500 hover:text-slate-800">
          Cancel & Exit
        </Link>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl text-rose-700 text-xs">
          {error}
        </div>
      )}

      {/* Step Content */}
      <Card className="p-6 border-slate-200/80 shadow-xs space-y-6">
        {step === 1 && (
          <div className="space-y-4">
            <Input
              label="Listing Title"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Spacious 2BHK Near Sony Signal, Koramangala"
            />
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Accommodation Category</label>
              <select
                value={propertyCategory}
                onChange={(e) => setPropertyCategory(e.target.value)}
                className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
              >
                <option value="apartment">Entire Apartment / Flat</option>
                <option value="independent_house">Independent House / Villa</option>
                <option value="pg">PG Accommodation</option>
                <option value="co_living">Co-Living Space</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Description</label>
              <textarea
                rows={4}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Highlight location advantages, public transport connectivity, and tenant preferences..."
                className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <Input label="City" required value={city} onChange={(e) => setCity(e.target.value)} />
              <Input label="State" required value={state} onChange={(e) => setState(e.target.value)} />
            </div>
            <Input
              label="Locality / Sector (Publicly Visible)"
              required
              value={locality}
              onChange={(e) => setLocality(e.target.value)}
              placeholder="e.g. HSR Layout Sector 4"
            />
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Exact Flat & Building Address (Masked until confirmed visit)
              </label>
              <input
                type="text"
                value={addressExact}
                onChange={(e) => setAddressExact(e.target.value)}
                placeholder="e.g. Flat 302, Green Glen Apartments, 14th Main"
                className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-sm"
              />
              <span className="text-[11px] text-slate-400 mt-1 block">
                Protected by Privacy Engine: Only shown to seekers with confirmed appointments.
              </span>
            </div>
            <Input label="Pincode" required value={postalCode} onChange={(e) => setPostalCode(e.target.value)} />
          </div>
        )}

        {step === 3 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Unit Configuration</label>
              <select
                value={configuration}
                onChange={(e) => setConfiguration(e.target.value)}
                className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
              >
                <option value="1RK">1RK</option>
                <option value="1BHK">1BHK</option>
                <option value="2BHK">2BHK</option>
                <option value="3BHK">3BHK</option>
                <option value="4BHK_plus">4BHK+</option>
                <option value="studio">Studio</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Furnishing Status</label>
              <select
                value={furnishingStatus}
                onChange={(e) => setFurnishingStatus(e.target.value)}
                className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
              >
                <option value="fully_furnished">Fully Furnished</option>
                <option value="semi_furnished">Semi-Furnished</option>
                <option value="unfurnished">Unfurnished</option>
              </select>
            </div>
            <Input
              label="Total Bedrooms"
              type="number"
              value={totalBedrooms}
              onChange={(e) => setTotalBedrooms(e.target.value)}
            />
            <Input
              label="Total Bathrooms"
              type="number"
              value={totalBathrooms}
              onChange={(e) => setTotalBathrooms(e.target.value)}
            />
            <Input
              label="Max Occupancy Capacity"
              type="number"
              value={maxCapacity}
              onChange={(e) => setMaxCapacity(e.target.value)}
            />
          </div>
        )}

        {step === 4 && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-700">Configured Rooms</span>
              <Button size="sm" variant="outline" className="gap-1.5" onClick={addRoom}>
                <Plus className="w-3.5 h-3.5" />
                <span>Add Room</span>
              </Button>
            </div>

            {rooms.map((room, idx) => (
              <div key={room.id} className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-sm text-slate-900">Room {idx + 1}</h4>
                  {rooms.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeRoom(room.id)}
                      className="text-rose-500 hover:text-rose-700 text-xs flex items-center gap-1"
                    >
                      <Trash2 className="w-3.5 h-3.5" /> Remove
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <Input
                    label="Room Label"
                    value={room.name}
                    onChange={(e) => {
                      const updated = [...rooms];
                      updated[idx].name = e.target.value;
                      setRooms(updated);
                    }}
                  />
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Room Type</label>
                    <select
                      value={room.type}
                      onChange={(e) => {
                        const updated = [...rooms];
                        updated[idx].type = e.target.value as "private" | "shared";
                        setRooms(updated);
                      }}
                      className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
                    >
                      <option value="private">Private Room</option>
                      <option value="shared">Shared Room</option>
                    </select>
                  </div>
                  <Input
                    label="Room Rent (₹/mo)"
                    type="number"
                    value={String(room.rent)}
                    onChange={(e) => {
                      const updated = [...rooms];
                      updated[idx].rent = parseFloat(e.target.value) || 0;
                      setRooms(updated);
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}

        {step === 5 && (
          <div className="space-y-4">
            <p className="text-xs text-slate-500">
              Configure bed-level inventory allocation. Each bed can be leased individually or with the room.
            </p>
            {rooms.map((room) => (
              <div key={room.id} className="p-4 border border-slate-200 rounded-2xl space-y-3 bg-white">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Bed className="w-4 h-4 text-indigo-600" />
                    <span className="font-bold text-sm text-slate-900">{room.name}</span>
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => addBedToRoom(room.id)} className="text-xs">
                    + Add Bed
                  </Button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {room.beds.map((bed) => (
                    <div
                      key={bed.id}
                      className="p-3 bg-slate-50 border border-slate-200/80 rounded-xl flex items-center justify-between text-xs"
                    >
                      <div>
                        <span className="font-semibold text-slate-800">{bed.identifier}</span>
                        <span className="text-slate-400 block text-[10px] mt-0.5">
                          {formatCurrency(bed.rent, "INR")}/mo • Available
                        </span>
                      </div>
                      {room.beds.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeBedFromRoom(room.id, bed.id)}
                          className="text-rose-500 p-1"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {step === 6 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              label="Entire Property Monthly Rent (₹ INR)"
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
            <div className="flex items-center space-x-2 pt-6">
              <input
                type="checkbox"
                id="bills"
                checked={billsIncluded}
                onChange={(e) => setBillsIncluded(e.target.checked)}
                className="w-4 h-4 text-indigo-600 rounded"
              />
              <label htmlFor="bills" className="text-xs font-semibold text-slate-700">
                Utility bills (Water, Electricity, Gas) included in rent
              </label>
            </div>
          </div>
        )}

        {step === 7 && (
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-2">Amenities Included</label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {["wifi", "power_backup", "lift", "security", "parking", "geyser", "air_conditioner", "washing_machine"].map((am) => (
                  <button
                    key={am}
                    type="button"
                    onClick={() => toggleAmenity(am)}
                    className={`p-2.5 rounded-xl border text-xs font-medium text-left capitalize transition-colors ${
                      amenities.includes(am)
                        ? "bg-indigo-50 border-indigo-300 text-indigo-700"
                        : "border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {am.replace(/_/g, " ")}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 pt-2 border-t border-slate-100">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Kitchen / Food Policy</label>
                <select
                  value={kitchenPolicy}
                  onChange={(e) => setKitchenPolicy(e.target.value)}
                  className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
                >
                  <option value="pure_veg">Strictly Pure Vegetarian Kitchen</option>
                  <option value="veg_and_egg">Vegetarian + Eggs Allowed</option>
                  <option value="veg_and_non_veg">Non-Vegetarian Cooking Permitted</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Smoking Policy</label>
                <select
                  value={smokingPolicy}
                  onChange={(e) => setSmokingPolicy(e.target.value)}
                  className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
                >
                  <option value="never">Smoke-Free Household</option>
                  <option value="balcony_only">Balcony / Outdoor Only</option>
                  <option value="permitted">Smoking Permitted</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {step === 8 && (
          <div className="space-y-4">
            <FileUpload
              bucket="properties"
              purpose="listing_gallery"
              label="Upload Property Photos"
              helperText="Upload real photos of bedrooms, living area, and bathrooms. JPEG, PNG, or WebP up to 10MB."
              onUploadSuccess={(res) => {
                setUploadedImages((prev) => [...prev, res.url]);
              }}
            />

            {uploadedImages.length > 0 && (
              <div className="grid grid-cols-3 gap-3 pt-2">
                {uploadedImages.map((imgUrl, i) => (
                  <div key={i} className="relative rounded-xl overflow-hidden h-24 border border-slate-200">
                    <img src={imgUrl} alt={`Uploaded ${i}`} className="w-full h-full object-cover" />
                    <button
                      type="button"
                      onClick={() => setUploadedImages(uploadedImages.filter((_, idx) => idx !== i))}
                      className="absolute top-1 right-1 bg-black/60 text-white p-1 rounded-full text-xs"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {step === 9 && (
          <div className="space-y-4 text-xs text-slate-700">
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-2">
              <h3 className="font-bold text-sm text-slate-900">{title || `${configuration} in ${locality}`}</h3>
              <p className="text-slate-500">{locality}, {city} — {postalCode}</p>
              <div className="flex gap-4 pt-2 font-semibold">
                <span>Rent: {formatCurrency(parseFloat(monthlyRent) || 0, "INR")}/mo</span>
                <span>Deposit: {formatCurrency(parseFloat(securityDeposit) || 0, "INR")}</span>
                <span>Rooms: {rooms.length}</span>
              </div>
            </div>
            <p className="text-slate-500 text-[11px]">
              By publishing, you confirm ownership or authorization to lease this accommodation in accordance with our terms of service and tenant verification policies.
            </p>
          </div>
        )}
      </Card>

      {/* Navigation Footer */}
      <div className="flex items-center justify-between pt-2">
        <Button
          variant="outline"
          size="md"
          disabled={step === 1 || isSubmitting}
          onClick={() => setStep((s) => s - 1)}
          className="gap-2"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back</span>
        </Button>

        {step < 9 ? (
          <Button
            variant="primary"
            size="md"
            onClick={() => setStep((s) => s + 1)}
            className="gap-2"
          >
            <span>Continue</span>
            <ArrowRight className="w-4 h-4" />
          </Button>
        ) : (
          <Button
            variant="primary"
            size="md"
            isLoading={isSubmitting}
            onClick={handleFinalSubmit}
            className="gap-2 bg-emerald-600 hover:bg-emerald-700 shadow-md"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>Publish Property Listing</span>
          </Button>
        )}
      </div>
    </div>
  );
}
