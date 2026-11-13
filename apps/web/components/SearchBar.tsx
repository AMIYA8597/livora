"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, MapPin, DollarSign, Calendar } from "lucide-react";
import { Button } from "@flatmate/ui";

export const SearchBar: React.FC = () => {
  const router = useRouter();
  const [city, setCity] = useState("San Francisco");
  const [budget, setBudget] = useState("1800");

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    router.push(`/properties?city=${encodeURIComponent(city)}&max_rent=${budget}`);
  };

  return (
    <form
      onSubmit={handleSearch}
      className="bg-white p-3 sm:p-4 rounded-2xl shadow-xl shadow-slate-200/60 border border-slate-200/80 max-w-4xl mx-auto flex flex-col md:flex-row gap-3 items-stretch md:items-center"
    >
      {/* Location */}
      <div className="flex-1 flex items-center px-3 py-2 bg-slate-50 rounded-xl border border-slate-200/60 focus-within:ring-2 focus-within:ring-indigo-500 focus-within:bg-white transition-all">
        <MapPin className="w-5 h-5 text-indigo-500 mr-2 shrink-0" />
        <div className="w-full">
          <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Target Location
          </label>
          <input
            type="text"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder="City, Neighborhood or Zip"
            className="w-full bg-transparent text-sm font-semibold text-slate-800 placeholder-slate-400 focus:outline-none"
          />
        </div>
      </div>

      {/* Max Budget */}
      <div className="flex-1 flex items-center px-3 py-2 bg-slate-50 rounded-xl border border-slate-200/60 focus-within:ring-2 focus-within:ring-indigo-500 focus-within:bg-white transition-all">
        <DollarSign className="w-5 h-5 text-emerald-500 mr-2 shrink-0" />
        <div className="w-full">
          <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Max Monthly Budget
          </label>
          <input
            type="number"
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
            placeholder="e.g. 1500"
            className="w-full bg-transparent text-sm font-semibold text-slate-800 placeholder-slate-400 focus:outline-none"
          />
        </div>
      </div>

      {/* Move-in Date */}
      <div className="flex-1 flex items-center px-3 py-2 bg-slate-50 rounded-xl border border-slate-200/60 focus-within:ring-2 focus-within:ring-indigo-500 focus-within:bg-white transition-all">
        <Calendar className="w-5 h-5 text-indigo-500 mr-2 shrink-0" />
        <div className="w-full">
          <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Move-In Window
          </label>
          <input
            type="text"
            defaultValue="Anytime soon"
            className="w-full bg-transparent text-sm font-semibold text-slate-800 placeholder-slate-400 focus:outline-none"
          />
        </div>
      </div>

      {/* Action Button */}
      <Button type="submit" variant="primary" size="lg" className="md:w-auto w-full gap-2 py-3 px-6">
        <Search className="w-4 h-4" />
        <span>Find Matches</span>
      </Button>
    </form>
  );
};
