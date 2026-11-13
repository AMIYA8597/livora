"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { PropertyDTO } from "@flatmate/contracts";
import { apiClient } from "@/lib/api-client";
import { PropertyCard } from "@/components/PropertyCard";
import { Input, Button } from "@flatmate/ui";
import { Search, MapPin } from "lucide-react";

function PropertiesListContent() {
  const searchParams = useSearchParams();
  const [properties, setProperties] = useState<PropertyDTO[]>([]);
  const [city, setCity] = useState(searchParams.get("city") || "");
  const [maxRent, setMaxRent] = useState(searchParams.get("max_rent") || "");
  const [isLoading, setIsLoading] = useState(true);

  const fetchProperties = async () => {
    try {
      setIsLoading(true);
      const params: Record<string, any> = {};
      if (city) params.city = city;
      if (maxRent) params.max_rent = maxRent;

      const data = await apiClient<PropertyDTO[]>("/properties", { params });
      setProperties(data);
    } catch (err) {
      console.error("Failed to load properties:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProperties();
  }, []);

  const handleFilterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchProperties();
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Available Co-Living Spaces</h1>
        <p className="text-slate-500 text-sm mt-1">
          Explore private rooms and entire properties vetted for quality flatsharing.
        </p>
      </div>

      {/* Filter Bar */}
      <form onSubmit={handleFilterSubmit} className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs flex flex-wrap gap-3 items-center">
        <div className="flex-1 min-w-[200px]">
          <Input
            placeholder="Search by city (e.g. San Francisco)"
            value={city}
            onChange={(e) => setCity(e.target.value)}
          />
        </div>
        <div className="w-44">
          <Input
            placeholder="Max Rent ($)"
            type="number"
            value={maxRent}
            onChange={(e) => setMaxRent(e.target.value)}
          />
        </div>
        <Button type="submit" variant="primary" className="gap-2">
          <Search className="w-4 h-4" />
          <span>Apply Filters</span>
        </Button>
      </form>

      {/* Results Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-pulse">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <div key={n} className="bg-slate-200 h-80 rounded-2xl" />
          ))}
        </div>
      ) : properties.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200/80 p-12 text-center max-w-lg mx-auto">
          <MapPin className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-800">No properties match your filter</h3>
          <p className="text-xs text-slate-500 mt-1">Try expanding your budget or searching in a nearby city.</p>
          <Button variant="outline" size="sm" className="mt-4" onClick={() => { setCity(""); setMaxRent(""); fetchProperties(); }}>
            Reset Filters
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {properties.map((prop) => (
            <PropertyCard key={prop.id} property={prop} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function PropertiesDirectoryPage() {
  return (
    <Suspense fallback={
      <div className="max-w-7xl mx-auto px-4 py-10">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-slate-200 rounded w-1/4"></div>
          <div className="h-4 bg-slate-200 rounded w-1/2"></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-6">
            <div className="h-64 bg-slate-200 rounded-2xl"></div>
            <div className="h-64 bg-slate-200 rounded-2xl"></div>
            <div className="h-64 bg-slate-200 rounded-2xl"></div>
          </div>
        </div>
      </div>
    }>
      <PropertiesListContent />
    </Suspense>
  );
}
