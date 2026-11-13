"use client";

import React, { useState, useEffect } from "react";
import { ProfileDTO } from "@flatmate/contracts";
import { apiClient } from "@/lib/api-client";
import { FlatmateCard } from "@/components/FlatmateCard";
import { Input, Button } from "@flatmate/ui";
import { Search, Users, Sun, Moon, Sparkles } from "lucide-react";

export default function FlatmatesDirectoryPage() {
  const [seekers, setSeekers] = useState<any[]>([]);
  const [city, setCity] = useState("");
  const [maxBudget, setMaxBudget] = useState("");
  const [sleepSchedule, setSleepSchedule] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  const fetchFlatmates = async () => {
    try {
      setIsLoading(true);
      const params: Record<string, any> = {};
      if (city) params.city = city;
      if (maxBudget) params.max_budget = maxBudget;
      if (sleepSchedule) params.sleep_schedule = sleepSchedule;

      const data = await apiClient<any[]>("/flatmates/search", { params });
      setSeekers(data);
    } catch (err) {
      console.error("Failed to load flatmates:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchFlatmates();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      <div>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Verified Flatmates</h1>
        <p className="text-slate-500 text-sm mt-1">
          Connect with compatible roommates searching for rooms or teaming up for new leases.
        </p>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs flex flex-wrap gap-3 items-center">
        <div className="flex-1 min-w-[200px]">
          <Input
            placeholder="Filter by city (e.g. San Francisco)"
            value={city}
            onChange={(e) => setCity(e.target.value)}
          />
        </div>
        <div className="w-40">
          <Input
            placeholder="Max Budget ($)"
            type="number"
            value={maxBudget}
            onChange={(e) => setMaxBudget(e.target.value)}
          />
        </div>
        <div className="flex gap-1.5">
          <button
            type="button"
            onClick={() => setSleepSchedule(sleepSchedule === "early_bird" ? "" : "early_bird")}
            className={`px-3 py-2 rounded-xl text-xs font-semibold flex items-center space-x-1 border transition-all ${
              sleepSchedule === "early_bird"
                ? "bg-amber-50 border-amber-400 text-amber-700 shadow-2xs"
                : "border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
          >
            <Sun className="w-3.5 h-3.5" />
            <span>Early Birds</span>
          </button>
          <button
            type="button"
            onClick={() => setSleepSchedule(sleepSchedule === "night_owl" ? "" : "night_owl")}
            className={`px-3 py-2 rounded-xl text-xs font-semibold flex items-center space-x-1 border transition-all ${
              sleepSchedule === "night_owl"
                ? "bg-indigo-50 border-indigo-400 text-indigo-700 shadow-2xs"
                : "border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
          >
            <Moon className="w-3.5 h-3.5" />
            <span>Night Owls</span>
          </button>
        </div>
        <Button variant="primary" onClick={fetchFlatmates}>
          Search
        </Button>
      </div>

      {/* Flatmate Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-pulse">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <div key={n} className="bg-slate-200 h-64 rounded-2xl" />
          ))}
        </div>
      ) : seekers.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200/80 p-12 text-center max-w-lg mx-auto">
          <Users className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-800">No flatmates found</h3>
          <p className="text-xs text-slate-500 mt-1">Try relaxing your filters or checking a different neighborhood.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {seekers.map((seeker) => (
            <FlatmateCard
              key={seeker.user_id}
              profile={seeker}
              isVerified={seeker.is_verified}
              matchScore={92}
            />
          ))}
        </div>
      )}
    </div>
  );
}
