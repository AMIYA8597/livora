"use client";

import React, { useState } from "react";
import { useApiQuery } from "@/hooks/useApiQuery";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api-client";
import { PGBuildingDTO, PropertyDTO } from "@flatmate/contracts";
import { Card, Button, Input, Badge, Modal, ErrorState } from "@flatmate/ui";
import { formatCurrency } from "@/lib/utils";
import {
  Building2,
  Plus,
  Utensils,
  Clock,
  ShieldCheck,
  CheckCircle2,
  Lock,
  Layers,
  MapPin,
  Home,
  Bed,
  Users,
} from "lucide-react";

export default function PGManagePage() {
  const { isAuthenticated, isLoading: authLoading, isPgOperator, isAdmin, user } = useAuth();
  const buildingsQuery = useApiQuery<PGBuildingDTO[]>(authLoading ? null : "/pg/buildings");
  const propertiesQuery = useApiQuery<PropertyDTO[]>(authLoading ? null : "/properties");
  const buildings = buildingsQuery.data ?? [];
  const properties = propertiesQuery.data ?? [];
  const isLoading = authLoading || buildingsQuery.isLoading || propertiesQuery.isLoading;
  const loadError = buildingsQuery.error || propertiesQuery.error;
  const loadData = () => {
    buildingsQuery.refetch();
    propertiesQuery.refetch();
  };
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isFloorModalOpen, setIsFloorModalOpen] = useState(false);
  const [selectedBuildingId, setSelectedBuildingId] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // PG Building Form State
  // Defaults to the first listing until the operator picks one.
  const [selectedPropertyId, setPropertyId] = useState("");
  const propertyId = selectedPropertyId || properties[0]?.id || "";
  const [buildingName, setBuildingName] = useState("");
  const [pgType, setPgType] = useState("coed");
  const [totalFloors, setTotalFloors] = useState("3");
  const [foodIncluded, setFoodIncluded] = useState(true);
  const [mealType, setMealType] = useState("veg_and_non_veg");
  const [mealsPerDay, setMealsPerDay] = useState("3");
  const [curfewTime, setCurfewTime] = useState("22:30");
  const [noticePeriod, setNoticePeriod] = useState("30");
  const [biometricEntry, setBiometricEntry] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Floor Form State
  const [floorNumber, setFloorNumber] = useState("1");
  const [floorGender, setFloorGender] = useState("coed");
  const [floorRooms, setFloorRooms] = useState("4");
  const [isSubmittingFloor, setIsSubmittingFloor] = useState(false);


  const handleCreateBuilding = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!propertyId) {
      alert("Please select a base property listing.");
      return;
    }
    try {
      setIsSubmitting(true);
      await apiClient("/pg/buildings", {
        method: "POST",
        body: JSON.stringify({
          property_id: propertyId,
          building_name: buildingName,
          pg_type: pgType,
          total_floors: parseInt(totalFloors, 10),
          food_included: foodIncluded,
          meal_type: mealType,
          meals_served_per_day: parseInt(mealsPerDay, 10),
          gate_closing_time: curfewTime || undefined,
          notice_period_days: parseInt(noticePeriod, 10),
          biometric_entry: biometricEntry,
        }),
      });
      setIsModalOpen(false);
      setActionNotice("PG Building registered successfully!");
      setTimeout(() => setActionNotice(null), 3000);
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to register PG building");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAddFloor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBuildingId) return;

    try {
      setIsSubmittingFloor(true);
      await apiClient(`/pg/buildings/${selectedBuildingId}/floors`, {
        method: "POST",
        body: JSON.stringify({
          floor_number: parseInt(floorNumber, 10),
          gender_restriction: floorGender,
          total_rooms: parseInt(floorRooms, 10),
        }),
      });
      setIsFloorModalOpen(false);
      setActionNotice("Floor added to PG building!");
      setTimeout(() => setActionNotice(null), 3000);
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to add floor");
    } finally {
      setIsSubmittingFloor(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-1.5 bg-indigo-50 text-indigo-700 text-xs font-semibold px-3 py-1 rounded-full mb-2">
            <Building2 className="w-3.5 h-3.5" />
            <span>PG & Co-Living Operations</span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">PG Management Console</h1>
          <p className="text-slate-500 text-sm mt-1">
            Manage commercial Paying Guest buildings, floor wings, gender policies, meal menus, and curfew rules.
          </p>
        </div>

        <Button variant="primary" className="gap-2 shadow-md" onClick={() => setIsModalOpen(true)}>
          <Plus className="w-4 h-4" />
          <span>Register PG Building</span>
        </Button>
      </div>

      {actionNotice && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center space-x-2 text-xs text-emerald-800">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Buildings List */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[1, 2].map((i) => (
            <div key={i} className="h-64 bg-slate-100 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : loadError ? (
        <ErrorState title="Couldn't load your PG buildings" message={loadError.message} onRetry={loadData} />
      ) : buildings.length === 0 ? (
        <Card className="p-12 text-center border-slate-200/80 max-w-lg mx-auto">
          <Building2 className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-800">No PG Buildings Registered</h3>
          <p className="text-xs text-slate-500 mt-1">
            Register your PG building to configure floor plans, meal plans, and automated tenant occupancy.
          </p>
          <Button variant="primary" size="sm" className="mt-4" onClick={() => setIsModalOpen(true)}>
            Register First PG
          </Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {buildings.map((b) => (
            <Card key={b.id} className="p-6 border-slate-200/80 space-y-4 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-extrabold text-slate-900 text-lg">{b.building_name}</h3>
                  <div className="flex items-center space-x-2 text-xs text-slate-500 mt-1">
                    <span className="capitalize">{b.pg_type} PG</span>
                    <span>•</span>
                    <span>{b.total_floors} Floors</span>
                  </div>
                </div>
                <Badge variant={b.pg_type === "female_only" ? "danger" : "info"} size="sm">
                  {b.pg_type.replace(/_/g, " ").toUpperCase()}
                </Badge>
              </div>

              {/* Policy Badges */}
              <div className="grid grid-cols-2 gap-3 text-xs bg-slate-50 p-3 rounded-xl border border-slate-100">
                <div className="flex items-center space-x-2">
                  <Utensils className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                  <span>
                    {b.food_included
                      ? `${b.meals_served_per_day} Meals/day (${b.meal_type})`
                      : "Self Cooking"}
                  </span>
                </div>
                <div className="flex items-center space-x-2">
                  <Clock className="w-4 h-4 text-indigo-600 flex-shrink-0" />
                  <span>Gate closes at {b.gate_closing_time || "No curfew"}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <Lock className="w-4 h-4 text-purple-600 flex-shrink-0" />
                  <span>{b.biometric_entry ? "Biometric Access" : "Keycard Entry"}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <ShieldCheck className="w-4 h-4 text-teal-600 flex-shrink-0" />
                  <span>{b.notice_period_days} Days Notice</span>
                </div>
              </div>

              {/* Floors and Wings */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-slate-700 uppercase">Configured Floors</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-xs"
                    onClick={() => {
                      setSelectedBuildingId(b.id);
                      setIsFloorModalOpen(true);
                    }}
                  >
                    + Add Floor
                  </Button>
                </div>

                {b.floors && b.floors.length > 0 ? (
                  <div className="grid grid-cols-2 gap-2">
                    {b.floors.map((floor) => (
                      <div
                        key={floor.id}
                        className="p-2.5 bg-white border border-slate-200 rounded-xl text-xs flex justify-between items-center"
                      >
                        <span className="font-semibold text-slate-800">Floor {floor.floor_number}</span>
                        <span className="text-[10px] text-slate-400 capitalize">
                          {floor.gender_restriction} • {floor.total_rooms} Rms
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 italic">No floors configured yet.</p>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Register Building Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Register PG Commercial Building"
        description="Add a Paying Guest property with operational policies."
      >
        <form onSubmit={handleCreateBuilding} className="space-y-4 mt-2">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Select Base Property Listing
            </label>
            <select
              value={propertyId}
              onChange={(e) => setPropertyId(e.target.value)}
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

          <Input
            label="PG Building Name"
            required
            value={buildingName}
            onChange={(e) => setBuildingName(e.target.value)}
            placeholder="e.g. Starlight Luxury Co-Living & PG"
          />

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">PG Classification</label>
              <select
                value={pgType}
                onChange={(e) => setPgType(e.target.value)}
                className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
              >
                <option value="coed">Co-ed PG</option>
                <option value="female_only">Women Only PG</option>
                <option value="male_only">Men Only PG</option>
              </select>
            </div>
            <Input
              label="Total Floors"
              type="number"
              value={totalFloors}
              onChange={(e) => setTotalFloors(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Meal Service</label>
              <select
                value={mealType}
                onChange={(e) => setMealType(e.target.value)}
                className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
              >
                <option value="veg_and_non_veg">Veg & Non-Veg Included</option>
                <option value="pure_veg">Strictly Pure Veg</option>
                <option value="none">No Food / Self Service</option>
              </select>
            </div>
            <Input
              label="Curfew / Gate Closing"
              type="time"
              value={curfewTime}
              onChange={(e) => setCurfewTime(e.target.value)}
            />
          </div>

          <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isSubmitting}>
            Save PG Building
          </Button>
        </form>
      </Modal>

      {/* Add Floor Modal */}
      <Modal
        isOpen={isFloorModalOpen}
        onClose={() => setIsFloorModalOpen(false)}
        title="Configure PG Floor"
        description="Add a floor wing with gender restrictions and room count."
      >
        <form onSubmit={handleAddFloor} className="space-y-4 mt-2">
          <Input
            label="Floor Number"
            type="number"
            required
            value={floorNumber}
            onChange={(e) => setFloorNumber(e.target.value)}
          />
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Floor Wing Restriction</label>
            <select
              value={floorGender}
              onChange={(e) => setFloorGender(e.target.value)}
              className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
            >
              <option value="coed">Co-ed Floor</option>
              <option value="female_only">Female Wing</option>
              <option value="male_only">Male Wing</option>
            </select>
          </div>
          <Input
            label="Total Rooms on this Floor"
            type="number"
            required
            value={floorRooms}
            onChange={(e) => setFloorRooms(e.target.value)}
          />
          <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isSubmittingFloor}>
            Add Floor Wing
          </Button>
        </form>
      </Modal>
    </div>
  );
}
