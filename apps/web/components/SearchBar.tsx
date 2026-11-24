"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, MapPin, IndianRupee, Home, LocateFixed } from "lucide-react";
import { Button } from "@flatmate/ui";
import { CitySelect } from "@/features/locations/CitySelect";
import { useCities } from "@/hooks/useCities";
import { popularCities } from "@/lib/locations";

export const SearchBar: React.FC = () => {
  const router = useRouter();
  const { cities } = useCities();
  const [city, setCity] = useState("");
  const [budget, setBudget] = useState("30000");
  const [category, setCategory] = useState("all");

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const queryParts: string[] = [];
    if (city.trim()) queryParts.push(`city=${encodeURIComponent(city.trim())}`);
    if (budget.trim()) queryParts.push(`max_rent=${encodeURIComponent(budget.trim())}`);
    if (category !== "all") queryParts.push(`category=${encodeURIComponent(category)}`);
    router.push(`/properties${queryParts.length > 0 ? `?${queryParts.join("&")}` : ""}`);
  };

  return (
    <div className="w-full max-w-4xl mx-auto space-y-3">
      <form
        onSubmit={handleSearch}
        className="bg-white p-3 sm:p-4 rounded-2xl shadow-lg border border-warm-200 flex flex-col md:flex-row gap-3 items-stretch md:items-center"
      >
        {/* City Select */}
        <div className="flex-1 flex items-center px-3.5 py-2.5 bg-warm-50/70 rounded-xl border border-warm-200 focus-within:ring-2 focus-within:ring-brand-500 focus-within:bg-white transition-all">
          <MapPin className="w-5 h-5 text-forest mr-2.5 shrink-0" />
          <div className="w-full text-left">
            <label htmlFor="search-city" className="block text-[10px] font-bold uppercase tracking-wider text-charcoal-muted">
              City
            </label>
            <CitySelect
              id="search-city"
              cities={cities}
              value={city}
              placeholder="Any city in India"
              onChange={(c) => setCity(c?.name ?? "")}
              className="w-full bg-transparent text-sm font-semibold text-charcoal focus:outline-none cursor-pointer"
            />
          </div>
        </div>

        {/* Max Rent (INR) */}
        <div className="flex-1 flex items-center px-3.5 py-2.5 bg-warm-50/70 rounded-xl border border-warm-200 focus-within:ring-2 focus-within:ring-brand-500 focus-within:bg-white transition-all">
          <IndianRupee className="w-5 h-5 text-forest mr-2.5 shrink-0" />
          <div className="w-full text-left">
            <label className="block text-[10px] font-bold uppercase tracking-wider text-charcoal-muted">
              Max Monthly Budget
            </label>
            <input
              type="number"
              step="1000"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              placeholder="e.g. 30000"
              className="w-full bg-transparent text-sm font-semibold text-charcoal placeholder-slate-400 focus:outline-none"
            />
          </div>
        </div>

        {/* Accommodation Category */}
        <div className="flex-1 flex items-center px-3.5 py-2.5 bg-warm-50/70 rounded-xl border border-warm-200 focus-within:ring-2 focus-within:ring-brand-500 focus-within:bg-white transition-all">
          <Home className="w-5 h-5 text-forest mr-2.5 shrink-0" />
          <div className="w-full text-left">
            <label className="block text-[10px] font-bold uppercase tracking-wider text-charcoal-muted">
              Accommodation Type
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full bg-transparent text-sm font-semibold text-charcoal focus:outline-none cursor-pointer"
            >
              <option value="all">Any Category</option>
              <option value="flat">Entire Flat / Apartment</option>
              <option value="room">Private Room in Flat</option>
              <option value="pg">PG & Co-Living</option>
            </select>
          </div>
        </div>

        {/* Submit */}
        <Button
          type="submit"
          variant="primary"
          size="lg"
          className="md:w-auto w-full py-3.5 px-6 font-semibold shadow-sm"
        >
          <Search className="w-4 h-4 mr-2" />
          <span>Find Homes</span>
        </Button>
      </form>

      {/* Quick City Filter Chips */}
      <div className="flex items-center justify-center flex-wrap gap-1.5 text-xs text-charcoal-muted pt-1">
        <button
          type="button"
          onClick={() => router.push("/properties?near=1")}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-forest text-white hover:bg-forest-light font-semibold transition-colors mr-1"
        >
          <LocateFixed className="w-3.5 h-3.5" aria-hidden="true" />
          Near me
        </button>
        <span className="font-medium mr-1">Popular:</span>
        {popularCities(cities).map((c) => (
          <button
            key={c.slug}
            type="button"
            onClick={() => {
              setCity(c.name);
              router.push(`/properties?city=${encodeURIComponent(c.name)}`);
            }}
            className="px-2.5 py-1 rounded-full bg-white hover:bg-pale-green/40 border border-warm-200 text-charcoal transition-colors"
          >
            {c.name}
          </button>
        ))}
      </div>
    </div>
  );
};
