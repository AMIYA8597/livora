"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useApiQuery } from "@/hooks/useApiQuery";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api-client";
import { PGBuildingDTO, PropertyDTO } from "@flatmate/contracts";
import { Card, Button, Input, Badge, Modal, EmptyState, ErrorState } from "@flatmate/ui";
import {
  Building2,
  Plus,
  Utensils,
  Clock,
  ShieldCheck,
  CheckCircle2,
  Layers,
  MapPin,
  Home,
  Shield,
} from "lucide-react";

export default function PGManagementPage() {
  const { isAuthenticated, isLoading: authLoading, isPgOperator, isAdmin } = useAuth();
  const router = useRouter();
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
      alert(err.message || "Failed to create PG building");
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
          <div className="inline-flex items-center gap-1.5 bg-forest-pale text-forest text-xs font-semibold px-3 py-1 rounded-full mb-2">
            <Building2 className="w-3.5 h-3.5" />
            <span>Paying Guest (PG) & Hostel Hub</span>
          </div>
          <h1 className="text-3xl font-extrabold text-charcoal tracking-tight">PG & Co-Living Operations</h1>
          <p className="text-charcoal-muted text-sm mt-1">
            Manage multi-floor buildings, mess meal plans, curfew rules, and bed allocations.
          </p>
        </div>

        {isAuthenticated && (
          <Button
            variant="primary"
            size="md"
            className="gap-2 shadow-sm"
            onClick={() => setIsModalOpen(true)}
          >
            <Plus className="w-4 h-4" />
            <span>Register PG Building</span>
          </Button>
        )}
      </div>

      {actionNotice && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-2xl text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Buildings Grid */}
      <div className="space-y-4">
        <h2 className="text-xl font-bold text-charcoal">Registered PG Buildings</h2>

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-pulse">
            {[1, 2, 3].map((n) => (
              <div key={n} className="bg-slate-200 h-64 rounded-2xl" />
            ))}
          </div>
        ) : loadError ? (
          <ErrorState title="Couldn't load PG buildings" message={loadError.message} onRetry={loadData} />
        ) : buildings.length === 0 ? (
          <EmptyState
            title="No PG buildings registered yet"
            description="PG operators can add their co-living facilities, meal inclusions, and curfew policies."
            actionLabel={isAuthenticated ? "Register PG Building" : "Sign In to Register"}
            onAction={() => (isAuthenticated ? setIsModalOpen(true) : router.push("/login"))}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {buildings.map((b) => (
              <Card key={b.id} className="p-6 border-slate-200/80 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Badge variant="forest" className="uppercase text-[10px] tracking-wider">
                      {b.pg_type} PG
                    </Badge>
                    <span className="text-xs text-charcoal-muted flex items-center gap-1">
                      <Layers className="w-3.5 h-3.5 text-forest" /> {b.total_floors} Floors
                    </span>
                  </div>
                  <h3 className="font-bold text-charcoal text-lg mb-2">{b.building_name}</h3>

                  <div className="space-y-1.5 text-xs text-charcoal-muted">
                    <div className="flex items-center gap-2">
                      <Utensils className="w-3.5 h-3.5 text-forest" />
                      <span>{b.food_included ? `${b.meals_served_per_day} Meals/day (${b.meal_type.replace(/_/g, " ")})` : "Self Cooking / No Food"}</span>
                    </div>
                    {b.gate_closing_time && (
                      <div className="flex items-center gap-2">
                        <Clock className="w-3.5 h-3.5 text-amber-600" />
                        <span>Curfew / Gate Closes: {b.gate_closing_time}</span>
                      </div>
                    )}
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="w-3.5 h-3.5 text-forest" />
                      <span>{b.biometric_entry ? "Biometric Security" : "Standard Key Access"} • {b.notice_period_days}d Notice</span>
                    </div>
                  </div>
                </div>

                <div className="pt-4 border-t border-slate-100 flex items-center justify-between mt-4">
                  <span className="text-xs text-charcoal-muted">{b.floors?.length ?? 0} Floors Configured</span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setSelectedBuildingId(b.id);
                      setIsFloorModalOpen(true);
                    }}
                  >
                    Add Floor
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Modal: Register PG Building */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Register PG Building"
        description="Add a new paying guest accommodation facility."
      >
        <form onSubmit={handleCreateBuilding} className="space-y-4 mt-2">
          <div>
            <label className="block text-xs font-semibold text-charcoal mb-1">Select Property</label>
            <select
              value={propertyId}
              onChange={(e) => setPropertyId(e.target.value)}
              required
              className="w-full text-xs rounded-xl border border-slate-200 p-2.5 bg-white"
            >
              {properties.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title} ({p.city})
                </option>
              ))}
            </select>
          </div>

          <Input
            label="Building Name"
            value={buildingName}
            onChange={(e) => setBuildingName(e.target.value)}
            placeholder="e.g. Green Oasis PG for Professionals"
            required
          />

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1">PG Type</label>
              <select
                value={pgType}
                onChange={(e) => setPgType(e.target.value)}
                className="w-full text-xs rounded-xl border border-slate-200 p-2.5 bg-white"
              >
                <option value="coed">Co-Ed (All Genders)</option>
                <option value="ladies">Ladies PG Only</option>
                <option value="gents">Gents PG Only</option>
              </select>
            </div>
            <Input
              label="Total Floors"
              type="number"
              value={totalFloors}
              onChange={(e) => setTotalFloors(e.target.value)}
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1">Food Inclusions</label>
              <select
                value={foodIncluded ? "yes" : "no"}
                onChange={(e) => setFoodIncluded(e.target.value === "yes")}
                className="w-full text-xs rounded-xl border border-slate-200 p-2.5 bg-white"
              >
                <option value="yes">Meals Included</option>
                <option value="no">Self Cooking / No Food</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1">Meal Type</label>
              <select
                value={mealType}
                onChange={(e) => setMealType(e.target.value)}
                className="w-full text-xs rounded-xl border border-slate-200 p-2.5 bg-white"
              >
                <option value="pure_veg">Pure Vegetarian</option>
                <option value="veg_and_non_veg">Veg & Non-Veg</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Curfew / Gate Closing Time"
              value={curfewTime}
              onChange={(e) => setCurfewTime(e.target.value)}
              placeholder="22:30"
            />
            <Input
              label="Notice Period (Days)"
              type="number"
              value={noticePeriod}
              onChange={(e) => setNoticePeriod(e.target.value)}
            />
          </div>

          <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isSubmitting}>
            Register PG Building
          </Button>
        </form>
      </Modal>

      {/* Modal: Add Floor */}
      <Modal
        isOpen={isFloorModalOpen}
        onClose={() => setIsFloorModalOpen(false)}
        title="Add Floor to PG Building"
        description="Allocate rooms and configure gender restrictions per floor."
      >
        <form onSubmit={handleAddFloor} className="space-y-4 mt-2">
          <Input
            label="Floor Level (0 for Ground, 1 for First)"
            type="number"
            value={floorNumber}
            onChange={(e) => setFloorNumber(e.target.value)}
            required
          />
          <div>
            <label className="block text-xs font-semibold text-charcoal mb-1">Gender Restriction</label>
            <select
              value={floorGender}
              onChange={(e) => setFloorGender(e.target.value)}
              className="w-full text-xs rounded-xl border border-slate-200 p-2.5 bg-white"
            >
              <option value="coed">Co-Ed</option>
              <option value="female_only">Female Only Floor</option>
              <option value="male_only">Male Only Floor</option>
            </select>
          </div>
          <Input
            label="Total Rooms on Floor"
            type="number"
            value={floorRooms}
            onChange={(e) => setFloorRooms(e.target.value)}
            required
          />
          <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isSubmittingFloor}>
            Add Floor
          </Button>
        </form>
      </Modal>
    </div>
  );
}
