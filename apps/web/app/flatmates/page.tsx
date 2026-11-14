"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { ProfileDTO } from "@flatmate/contracts";
import { apiClient } from "@/lib/api-client";
import { FlatmateCard } from "@/components/FlatmateCard";
import { Input, Button, Badge, Skeleton, EmptyState, ErrorState } from "@flatmate/ui";
import { useAuth } from "@/hooks/useAuth";
import { TOP_INDIAN_CITIES } from "@/lib/utils";
import {
  Search,
  Users,
  Sun,
  Moon,
  Sparkles,
  LogIn,
  RotateCcw,
  CheckCircle2,
} from "lucide-react";

export default function FlatmatesDirectoryPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [seekers, setSeekers] = useState<any[]>([]);
  const [city, setCity] = useState("Bengaluru");
  const [maxBudget, setMaxBudget] = useState("");
  const [sleepSchedule, setSleepSchedule] = useState("");
  const [diet, setDiet] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const fetchFlatmates = useCallback(async (targetCity?: string) => {
    if (!isAuthenticated) return;
    try {
      setIsLoading(true);
      setError(null);
      const params: Record<string, any> = {};
      const activeCity = targetCity !== undefined ? targetCity : city;
      if (activeCity) params.city = activeCity;
      if (maxBudget) params.max_budget = maxBudget;
      if (sleepSchedule) params.sleep_schedule = sleepSchedule;
      if (diet) params.diet = diet;

      const data = await apiClient<any[]>("/flatmates/search", { params });
      setSeekers(data || []);
    } catch (err: any) {
      console.error("Failed to load flatmates:", err);
      setError(err.message || "Failed to load flatmates");
      setSeekers([]);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, city, maxBudget, sleepSchedule, diet]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchFlatmates();
    }
  }, [isAuthenticated, fetchFlatmates]);

  const handleCitySelect = (selectedCity: string) => {
    const nextCity = city === selectedCity ? "" : selectedCity;
    setCity(nextCity);
    fetchFlatmates(nextCity);
  };

  const handleLike = async (userId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      const res = await apiClient<{ action: string; is_mutual_match: boolean }>("/matching/interactions", {
        method: "POST",
        body: JSON.stringify({
          target_user_id: userId,
          action: "like",
        }),
      });

      if (res.is_mutual_match) {
        setActionNotice("Mutual Match! You can now message them in Matches.");
      } else {
        setActionNotice("Profile liked! If they like you back, it's a match.");
      }
      setTimeout(() => setActionNotice(null), 3500);
    } catch (err: any) {
      setActionNotice(err.message || "Could not record interaction");
      setTimeout(() => setActionNotice(null), 3000);
    }
  };

  const handlePass = async (userId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await apiClient("/matching/interactions", {
        method: "POST",
        body: JSON.stringify({
          target_user_id: userId,
          action: "pass",
        }),
      });
      // Remove passed user from current list view
      setSeekers((prev) => prev.filter((s) => (s.user_id || s.id) !== userId));
      setActionNotice("Profile passed.");
      setTimeout(() => setActionNotice(null), 2000);
    } catch {
      // Ignored
    }
  };

  const handleReset = () => {
    setCity("");
    setMaxBudget("");
    setSleepSchedule("");
    setDiet("");
    setTimeout(() => {
      apiClient<any[]>("/flatmates/search")
        .then((res) => setSeekers(res || []))
        .catch(() => setSeekers([]));
    }, 0);
  };

  if (!authLoading && !isAuthenticated) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center space-y-6">
        <div className="w-16 h-16 rounded-2xl bg-pale-green/40 text-forest flex items-center justify-center mx-auto shadow-sm">
          <Users className="w-8 h-8" />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold text-charcoal tracking-tight">
            Verified Seeker Network
          </h1>
          <p className="text-sm text-charcoal-muted max-w-md mx-auto mt-2 leading-relaxed">
            In compliance with our community safety and privacy policy, the flatmate seeker directory
            is accessible only to authenticated members.
          </p>
        </div>
        <div className="flex justify-center gap-3 pt-2">
          <Link href="/login">
            <Button variant="primary" size="lg" className="gap-2">
              <LogIn className="w-4 h-4" />
              <span>Sign In to Browse</span>
            </Button>
          </Link>
          <Link href="/register">
            <Button variant="outline" size="lg">
              Create Account
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      <div>
        <h1 className="text-3xl font-extrabold text-charcoal tracking-tight">
          Find Compatible Flatmates
        </h1>
        <p className="text-charcoal-muted text-sm mt-1">
          Explore seekers matching your lifestyle rhythms, quiet hours, and budget in top Indian cities.
        </p>
      </div>

      {actionNotice && (
        <div className="p-3.5 bg-pale-green/30 border border-brand-200 text-forest rounded-2xl text-xs font-semibold flex items-center space-x-2 animate-in fade-in duration-150">
          <CheckCircle2 className="w-4 h-4 text-forest shrink-0" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="bg-white p-5 rounded-2xl border border-warm-200 shadow-xs space-y-4">
        {/* Popular Cities */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-semibold text-charcoal-muted mr-1">Top Cities:</span>
          {TOP_INDIAN_CITIES.map((c) => (
            <button
              key={c.name}
              type="button"
              onClick={() => handleCitySelect(c.name)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                city.toLowerCase() === c.name.toLowerCase()
                  ? "bg-forest text-white shadow-xs"
                  : "bg-warm-50 text-charcoal hover:bg-warm-100 border border-warm-200"
              }`}
            >
              {c.name}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <Input
            placeholder="Search by city (e.g. Bengaluru)"
            value={city}
            onChange={(e) => setCity(e.target.value)}
          />
          <Input
            placeholder="Max Budget (₹ / mo)"
            type="number"
            step="1000"
            value={maxBudget}
            onChange={(e) => setMaxBudget(e.target.value)}
          />
          <select
            value={diet}
            onChange={(e) => setDiet(e.target.value)}
            className="w-full text-xs font-semibold border border-slate-300 rounded-xl px-3.5 py-2.5 bg-white text-charcoal focus:ring-2 focus:ring-brand-500 cursor-pointer"
          >
            <option value="">Any Diet Preference</option>
            <option value="veg">Vegetarian</option>
            <option value="non_veg">Non-Vegetarian</option>
            <option value="jain">Jain</option>
            <option value="eggetarian">Eggetarian</option>
          </select>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setSleepSchedule(sleepSchedule === "early_bird" ? "" : "early_bird")}
              className={`flex-1 px-3 py-2 rounded-xl text-xs font-semibold flex items-center justify-center space-x-1 border transition-all ${
                sleepSchedule === "early_bird"
                  ? "bg-pale-green/40 border-forest text-forest shadow-2xs"
                  : "border-slate-200 text-charcoal hover:bg-slate-50"
              }`}
            >
              <Sun className="w-3.5 h-3.5" />
              <span>Early Birds</span>
            </button>
            <button
              type="button"
              onClick={() => setSleepSchedule(sleepSchedule === "night_owl" ? "" : "night_owl")}
              className={`flex-1 px-3 py-2 rounded-xl text-xs font-semibold flex items-center justify-center space-x-1 border transition-all ${
                sleepSchedule === "night_owl"
                  ? "bg-forest border-forest text-white shadow-2xs"
                  : "border-slate-200 text-charcoal hover:bg-slate-50"
              }`}
            >
              <Moon className="w-3.5 h-3.5" />
              <span>Night Owls</span>
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-slate-100">
          <button
            type="button"
            onClick={handleReset}
            className="text-xs text-charcoal-muted hover:text-forest flex items-center gap-1 font-medium"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset Filters</span>
          </button>

          <Button variant="primary" size="sm" onClick={() => fetchFlatmates()} className="gap-2">
            <Search className="w-4 h-4" />
            <span>Apply Filters</span>
          </Button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <ErrorState
          title="Could not load flatmates"
          message={error}
          onRetry={() => fetchFlatmates()}
        />
      )}

      {/* Flatmate Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <Skeleton key={n} variant="card" height={260} />
          ))}
        </div>
      ) : seekers.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No flatmates found matching your criteria"
          description="Try broadening your budget or searching in a different city."
          actionLabel="Reset Filters"
          onAction={handleReset}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {seekers.map((seeker) => (
            <FlatmateCard
              key={seeker.user_id || seeker.id}
              profile={seeker}
              isVerified={seeker.is_verified}
              onLike={handleLike}
              onPass={handlePass}
            />
          ))}
        </div>
      )}
    </div>
  );
}
