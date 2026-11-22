"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api-client";
import { PropertyDTO, RoomDTO, TenantMembershipDTO } from "@flatmate/contracts";
import { Card, Button, Input } from "@flatmate/ui";
import { formatCurrency } from "@/lib/utils";
import { Users, CheckCircle2, ArrowLeft, ShieldCheck, Home, Calendar } from "lucide-react";

export default function TenantVacancyCreatePage() {
  const router = useRouter();
  const { isAuthenticated, user } = useAuth();

  const [properties, setProperties] = useState<PropertyDTO[]>([]);
  const [selectedPropertyId, setSelectedPropertyId] = useState("");
  const [rooms, setRooms] = useState<RoomDTO[]>([]);
  const [selectedRoomId, setSelectedRoomId] = useState("");

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [expectedRent, setExpectedRent] = useState("12000");
  const [depositRequired, setDepositRequired] = useState("30000");
  const [preferredGender, setPreferredGender] = useState("any");
  const [vacantFrom, setVacantFrom] = useState(
    () => new Date(Date.now() + 7 * 86400000).toISOString().split("T")[0]
  );
  const [hasLandlordPermission, setHasLandlordPermission] = useState(true);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);

  useEffect(() => {
    async function loadProperties() {
      try {
        const props = await apiClient<PropertyDTO[]>("/properties");
        setProperties(props || []);
        if (props && props.length > 0) {
          setSelectedPropertyId(props[0].id);
          setRooms(props[0].rooms || []);
          if (props[0].rooms && props[0].rooms.length > 0) {
            setSelectedRoomId(props[0].rooms[0].id);
          }
        }
      } catch (err) {
        console.error("Failed to load properties:", err);
      }
    }
    loadProperties();
  }, []);

  const handlePropertyChange = (propId: string) => {
    setSelectedPropertyId(propId);
    const found = properties.find((p) => p.id === propId);
    if (found && found.rooms) {
      setRooms(found.rooms);
      if (found.rooms.length > 0) {
        setSelectedRoomId(found.rooms[0].id);
      }
    } else {
      setRooms([]);
      setSelectedRoomId("");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPropertyId) {
      setError("Please select the property where you currently reside.");
      return;
    }
    if (!hasLandlordPermission) {
      setError("Landlord consent or lease-replacement clause confirmation is required.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await apiClient("/tenants/vacancies", {
        method: "POST",
        body: JSON.stringify({
          property_id: selectedPropertyId,
          room_id: selectedRoomId || undefined,
          title: title || "Roommate Vacancy in Flatshare",
          description,
          vacant_from: vacantFrom,
          expected_rent: parseFloat(expectedRent),
          deposit_required: parseFloat(depositRequired),
          preferred_gender: preferredGender,
        }),
      });
      setIsSuccess(true);
    } catch (err: any) {
      setError(err.message || "Failed to create replacement vacancy posting");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSuccess) {
    return (
      <div className="max-w-xl mx-auto py-16 px-4 text-center space-y-4">
        <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-3xl flex items-center justify-center mx-auto">
          <CheckCircle2 className="w-8 h-8" />
        </div>
        <h2 className="text-2xl font-bold text-slate-900">Roommate Vacancy Posted!</h2>
        <p className="text-xs text-slate-500">
          Your vacancy has been published. Matching seekers with aligned lifestyle compatibility can now view and apply.
        </p>
        <div className="pt-4 flex justify-center space-x-3">
          <Link href="/tenants">
            <Button variant="primary">View My Vacancies</Button>
          </Link>
          <Link href="/dashboard">
            <Button variant="outline">Back to Dashboard</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-10 space-y-6">
      <Link
        href="/tenants"
        className="inline-flex items-center text-xs font-semibold text-slate-500 hover:text-slate-800"
      >
        <ArrowLeft className="w-4 h-4 mr-1" />
        Back to Tenancy Hub
      </Link>

      <div>
        <h1 className="text-2xl font-extrabold text-slate-900">Post a Roommate Vacancy</h1>
        <p className="text-xs text-slate-500 mt-1">
          Are you an existing tenant looking for a replacement flatmate to share your apartment or room rent?
        </p>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl text-rose-700 text-xs">
          {error}
        </div>
      )}

      <Card className="p-6 border-slate-200/80 shadow-xs space-y-4">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Select Your Leased Property
            </label>
            <select
              value={selectedPropertyId}
              onChange={(e) => handlePropertyChange(e.target.value)}
              required
              className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
            >
              {properties.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title} — {p.city}
                </option>
              ))}
            </select>
          </div>

          {rooms.length > 0 && (
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Select Specific Room / Bed Being Vacated
              </label>
              <select
                value={selectedRoomId}
                onChange={(e) => setSelectedRoomId(e.target.value)}
                className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
              >
                {rooms.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.room_name} ({r.room_type}) — {formatCurrency(r.room_rent, "INR")}/mo
                  </option>
                ))}
              </select>
            </div>
          )}

          <Input
            label="Posting Headline"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Need female flatmate for private master bedroom in 3BHK"
          />

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Flatmate Compatibility & Vibe Description
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe your current household rhythm, chores, cooking habits, and what you're looking for..."
              className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Share of Monthly Rent (₹)"
              type="number"
              required
              value={expectedRent}
              onChange={(e) => setExpectedRent(e.target.value)}
            />
            <Input
              label="Deposit Share (₹)"
              type="number"
              required
              value={depositRequired}
              onChange={(e) => setDepositRequired(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Preferred Flatmate Gender
              </label>
              <select
                value={preferredGender}
                onChange={(e) => setPreferredGender(e.target.value)}
                className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
              >
                <option value="any">Any / Open</option>
                <option value="female_only">Female Only</option>
                <option value="male_only">Male Only</option>
              </select>
            </div>
            <Input
              label="Available / Move-In Date"
              type="date"
              required
              value={vacantFrom}
              onChange={(e) => setVacantFrom(e.target.value)}
            />
          </div>

          <div className="p-3.5 bg-indigo-50 border border-indigo-100 rounded-xl flex items-start space-x-3 text-xs">
            <input
              type="checkbox"
              id="permission"
              checked={hasLandlordPermission}
              onChange={(e) => setHasLandlordPermission(e.target.checked)}
              className="w-4 h-4 text-indigo-600 rounded mt-0.5"
            />
            <label htmlFor="permission" className="text-slate-700">
              <span className="font-semibold block text-indigo-900">Lease Compliance Confirmation</span>
              I confirm that our existing lease agreement allows roommate replacement / sublease with landlord notification.
            </label>
          </div>

          <Button
            type="submit"
            variant="primary"
            size="md"
            className="w-full shadow-md"
            isLoading={isSubmitting}
          >
            Publish Vacancy
          </Button>
        </form>
      </Card>
    </div>
  );
}
