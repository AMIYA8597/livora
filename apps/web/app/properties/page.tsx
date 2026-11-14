"use client";

import React, { useState, useEffect, Suspense, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { PropertyDTO } from "@flatmate/contracts";
import { apiClient } from "@/lib/api-client";
import { PropertyCard } from "@/components/PropertyCard";
import { Input, Button, Badge, Skeleton, EmptyState, ErrorState, Pagination, Drawer } from "@flatmate/ui";
import { TOP_INDIAN_CITIES, formatCurrency } from "@/lib/utils";
import {
  Search,
  MapPin,
  SlidersHorizontal,
  RotateCcw,
  ArrowUpDown,
  X,
  Filter,
} from "lucide-react";

function PropertiesListContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Filter States initialized from URL
  const [city, setCity] = useState(searchParams.get("city") || "");
  const [locality, setLocality] = useState(searchParams.get("locality") || "");
  const [minRent, setMinRent] = useState(searchParams.get("min_rent") || "");
  const [maxRent, setMaxRent] = useState(searchParams.get("max_rent") || "");
  const [category, setCategory] = useState(searchParams.get("category") || "");
  const [configuration, setConfiguration] = useState(searchParams.get("config") || "");
  const [furnishing, setFurnishing] = useState(searchParams.get("furnishing") || "");
  const [sortBy, setSortBy] = useState(searchParams.get("sort") || "newest");
  const [page, setPage] = useState(Number(searchParams.get("page")) || 1);

  const [properties, setProperties] = useState<PropertyDTO[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [correlationId, setCorrelationId] = useState<string | undefined>();
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  const PAGE_SIZE = 9;

  const updateURLParams = useCallback(
    (params: Record<string, string | number>) => {
      const url = new URL(window.location.href);
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== "" && v !== null) {
          url.searchParams.set(k, String(v));
        } else {
          url.searchParams.delete(k);
        }
      });
      window.history.replaceState(null, "", url.toString());
    },
    []
  );

  const fetchProperties = useCallback(
    async (currentPage = page) => {
      try {
        setIsLoading(true);
        setError(null);
        setCorrelationId(undefined);

        const params: Record<string, any> = {
          limit: PAGE_SIZE,
          offset: (currentPage - 1) * PAGE_SIZE,
        };

        if (city.trim()) params.city = city.trim();
        if (minRent) params.min_rent = Number(minRent);
        if (maxRent) params.max_rent = Number(maxRent);
        if (category) params.property_category = category;
        if (configuration) params.configuration = configuration;

        const data = await apiClient<PropertyDTO[]>("/properties", { params });
        let list = data || [];

        // In-memory sorting for marketplace ordering
        if (sortBy === "price_asc") {
          list = [...list].sort((a, b) => Number(a.monthly_rent) - Number(b.monthly_rent));
        } else if (sortBy === "price_desc") {
          list = [...list].sort((a, b) => Number(b.monthly_rent) - Number(a.monthly_rent));
        }

        setProperties(list);
        setTotalCount(list.length >= PAGE_SIZE ? (currentPage + 1) * PAGE_SIZE : (currentPage - 1) * PAGE_SIZE + list.length);

        updateURLParams({
          city,
          locality,
          min_rent: minRent,
          max_rent: maxRent,
          category,
          config: configuration,
          furnishing,
          sort: sortBy,
          page: currentPage,
        });
      } catch (err: any) {
        console.error("Failed to load properties:", err);
        setError(err.message || "Failed to load properties");
        setCorrelationId(err.correlation_id || err.request_id);
        setProperties([]);
      } finally {
        setIsLoading(false);
      }
    },
    [city, locality, minRent, maxRent, category, configuration, furnishing, sortBy, page, updateURLParams]
  );

  useEffect(() => {
    fetchProperties(page);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, sortBy]);

  const handleFilterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    setMobileFiltersOpen(false);
    fetchProperties(1);
  };

  const handleCitySelect = (selectedCity: string) => {
    const nextCity = city === selectedCity ? "" : selectedCity;
    setCity(nextCity);
    setPage(1);
    setTimeout(() => {
      fetchProperties(1);
    }, 0);
  };

  const handleReset = () => {
    setCity("");
    setLocality("");
    setMinRent("");
    setMaxRent("");
    setCategory("");
    setConfiguration("");
    setFurnishing("");
    setSortBy("newest");
    setPage(1);
    const url = new URL(window.location.href);
    url.search = "";
    window.history.replaceState(null, "", url.toString());
    setTimeout(() => {
      apiClient<PropertyDTO[]>("/properties", { params: { limit: PAGE_SIZE, offset: 0 } })
        .then((res) => {
          setProperties(res || []);
          setTotalCount((res || []).length);
        })
        .catch(() => setProperties([]));
    }, 0);
  };

  // Active filters list for chips
  const activeFilters = [
    city && { label: `City: ${city}`, onRemove: () => { setCity(""); setPage(1); fetchProperties(1); } },
    minRent && { label: `Min: ${formatCurrency(minRent)}`, onRemove: () => { setMinRent(""); setPage(1); fetchProperties(1); } },
    maxRent && { label: `Max: ${formatCurrency(maxRent)}`, onRemove: () => { setMaxRent(""); setPage(1); fetchProperties(1); } },
    category && { label: `Category: ${category}`, onRemove: () => { setCategory(""); setPage(1); fetchProperties(1); } },
    configuration && { label: `Type: ${configuration}`, onRemove: () => { setConfiguration(""); setPage(1); fetchProperties(1); } },
  ].filter(Boolean) as { label: string; onRemove: () => void }[];

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-charcoal tracking-tight">
            Discover Verified Rental Properties
          </h1>
          <p className="text-charcoal-muted text-sm mt-1">
            Real apartments, private rooms, and PG accommodation across India&apos;s leading cities.
          </p>
        </div>

        {/* Sort & Mobile Filter Toggle */}
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1.5 bg-white border border-warm-200 px-3 py-2 rounded-xl text-xs font-semibold text-charcoal shadow-xs">
            <ArrowUpDown className="w-3.5 h-3.5 text-forest" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="bg-transparent focus:outline-none cursor-pointer"
            >
              <option value="newest">Newest First</option>
              <option value="price_asc">Rent: Low to High</option>
              <option value="price_desc">Rent: High to Low</option>
            </select>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setMobileFiltersOpen(true)}
            className="md:hidden flex items-center space-x-1.5"
          >
            <Filter className="w-3.5 h-3.5" />
            <span>Filters</span>
          </Button>
        </div>
      </div>

      {/* Desktop Filter Form */}
      <form
        onSubmit={handleFilterSubmit}
        className="hidden md:block bg-white p-5 rounded-2xl border border-warm-200 shadow-xs space-y-4"
      >
        {/* Popular Cities */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-semibold text-charcoal-muted mr-1">Popular:</span>
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

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <div>
            <label className="block text-[11px] font-semibold text-charcoal-muted uppercase tracking-wider mb-1">
              City / Locality
            </label>
            <Input
              placeholder="e.g. Bengaluru, HSR Layout"
              value={city}
              onChange={(e) => setCity(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-charcoal-muted uppercase tracking-wider mb-1">
              Min Rent (₹ / mo)
            </label>
            <Input
              placeholder="e.g. 10000"
              type="number"
              step="1000"
              value={minRent}
              onChange={(e) => setMinRent(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-charcoal-muted uppercase tracking-wider mb-1">
              Max Rent (₹ / mo)
            </label>
            <Input
              placeholder="e.g. 40000"
              type="number"
              step="1000"
              value={maxRent}
              onChange={(e) => setMaxRent(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-charcoal-muted uppercase tracking-wider mb-1">
              Category
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full text-xs font-semibold border border-slate-300 rounded-xl px-3.5 py-2.5 bg-white text-charcoal focus:outline-none focus:ring-2 focus:ring-brand-500 cursor-pointer"
            >
              <option value="">All Categories</option>
              <option value="apartment">Apartment / Flat</option>
              <option value="independent_house">Independent House</option>
              <option value="pg">Paying Guest (PG)</option>
              <option value="co_living">Co-Living Space</option>
              <option value="hostel">Hostel</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-charcoal-muted uppercase tracking-wider mb-1">
              Configuration
            </label>
            <select
              value={configuration}
              onChange={(e) => setConfiguration(e.target.value)}
              className="w-full text-xs font-semibold border border-slate-300 rounded-xl px-3.5 py-2.5 bg-white text-charcoal focus:outline-none focus:ring-2 focus:ring-brand-500 cursor-pointer"
            >
              <option value="">All Configurations</option>
              <option value="1RK">1RK</option>
              <option value="1BHK">1BHK</option>
              <option value="2RK">2RK</option>
              <option value="2BHK">2BHK</option>
              <option value="3BHK">3BHK</option>
              <option value="4BHK_plus">4BHK+</option>
              <option value="studio">Studio</option>
            </select>
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

          <Button type="submit" variant="primary" size="sm" className="gap-2">
            <Search className="w-4 h-4" />
            <span>Apply Filters</span>
          </Button>
        </div>
      </form>

      {/* Mobile Filters Drawer */}
      <Drawer
        isOpen={mobileFiltersOpen}
        onClose={() => setMobileFiltersOpen(false)}
        title="Filter Properties"
      >
        <form onSubmit={handleFilterSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-charcoal mb-1">City or Locality</label>
            <Input
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="e.g. Bengaluru, Mumbai"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1">Min Rent (₹)</label>
              <Input
                type="number"
                value={minRent}
                onChange={(e) => setMinRent(e.target.value)}
                placeholder="10000"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1">Max Rent (₹)</label>
              <Input
                type="number"
                value={maxRent}
                onChange={(e) => setMaxRent(e.target.value)}
                placeholder="50000"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-charcoal mb-1">Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full text-xs font-semibold border border-slate-300 rounded-xl px-3.5 py-2.5 bg-white text-charcoal"
            >
              <option value="">All Categories</option>
              <option value="apartment">Apartment</option>
              <option value="independent_house">Independent House</option>
              <option value="pg">PG</option>
              <option value="co_living">Co-Living</option>
              <option value="hostel">Hostel</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-charcoal mb-1">Configuration</label>
            <select
              value={configuration}
              onChange={(e) => setConfiguration(e.target.value)}
              className="w-full text-xs font-semibold border border-slate-300 rounded-xl px-3.5 py-2.5 bg-white text-charcoal"
            >
              <option value="">All Configurations</option>
              <option value="1RK">1RK</option>
              <option value="1BHK">1BHK</option>
              <option value="2BHK">2BHK</option>
              <option value="3BHK">3BHK</option>
              <option value="4BHK_plus">4BHK+</option>
            </select>
          </div>

          <div className="pt-4 flex items-center space-x-3">
            <Button
              type="button"
              variant="outline"
              onClick={handleReset}
              className="flex-1 justify-center"
            >
              Reset
            </Button>
            <Button type="submit" variant="primary" className="flex-1 justify-center">
              Apply
            </Button>
          </div>
        </form>
      </Drawer>

      {/* Applied Filter Chips */}
      {activeFilters.length > 0 && (
        <div className="flex items-center flex-wrap gap-2 pt-1">
          <span className="text-xs text-charcoal-muted font-medium">Applied:</span>
          {activeFilters.map((f, i) => (
            <span
              key={i}
              className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-pale-green/40 text-forest text-xs font-semibold border border-brand-200"
            >
              <span>{f.label}</span>
              <button
                type="button"
                onClick={f.onRemove}
                className="hover:text-forest-dark focus:outline-none"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </span>
          ))}
          <button
            type="button"
            onClick={handleReset}
            className="text-xs text-rose-600 hover:underline font-semibold ml-2"
          >
            Clear all
          </button>
        </div>
      )}

      {/* Error state */}
      {error && (
        <ErrorState
          title="Could not load properties"
          message={error}
          correlationId={correlationId}
          onRetry={() => fetchProperties(page)}
        />
      )}

      {/* Results Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <Skeleton key={n} variant="card" />
          ))}
        </div>
      ) : properties.length === 0 ? (
        <EmptyState
          icon={MapPin}
          title="No properties match your search"
          description="Try broadening your rent range, clearing filters, or searching in an adjacent locality."
          actionLabel="Reset Filters"
          onAction={handleReset}
        />
      ) : (
        <div className="space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {properties.map((prop) => (
              <PropertyCard key={prop.id} property={prop} />
            ))}
          </div>

          {/* Pagination Controls */}
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            onPageChange={(p) => setPage(p)}
          />
        </div>
      )}
    </div>
  );
}

export default function PropertiesDirectoryPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-7xl mx-auto px-4 py-10 space-y-6">
          <Skeleton variant="text" width="250px" height="32px" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Skeleton variant="card" />
            <Skeleton variant="card" />
            <Skeleton variant="card" />
          </div>
        </div>
      }
    >
      <PropertiesListContent />
    </Suspense>
  );
}
