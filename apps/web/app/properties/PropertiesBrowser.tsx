"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { PropertyDTO } from "@flatmate/contracts";
import { ApiError } from "@/lib/api-client";
import { useApiQuery } from "@/hooks/useApiQuery";
import { type AppliedFilters, filtersFromSearch, LISTINGS_PAGE_SIZE, listingQueryParams } from "@/lib/listing-query";
import { PropertyCard } from "@/components/PropertyCard";
import { Input, Button, Badge, Skeleton, EmptyState, ErrorState, Pagination, Drawer } from "@flatmate/ui";
import { formatCurrency } from "@/lib/utils";
import { CityDatalist } from "@/features/locations/CityDatalist";
import { useCities } from "@/hooks/useCities";
import { popularCities } from "@/lib/locations";
import {
  Search,
  MapPin,
  SlidersHorizontal,
  RotateCcw,
  ArrowUpDown,
  X,
  Filter,
} from "lucide-react";


export interface InitialListings {
  key: string;
  data: PropertyDTO[];
}

function PropertiesListContent({ initial }: { initial?: InitialListings }) {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Filter States initialized from URL
  const [q, setQ] = useState(searchParams.get("q") || "");
  const [city, setCity] = useState(searchParams.get("city") || "");
  const { cities } = useCities();
  const [locality, setLocality] = useState(searchParams.get("locality") || "");
  const [minRent, setMinRent] = useState(searchParams.get("min_rent") || "");
  const [maxRent, setMaxRent] = useState(searchParams.get("max_rent") || "");
  const [category, setCategory] = useState(searchParams.get("category") || "");
  const [configuration, setConfiguration] = useState(searchParams.get("config") || "");
  const [furnishing, setFurnishing] = useState(searchParams.get("furnishing") || "");
  const [sortBy, setSortBy] = useState(searchParams.get("sort") || "newest");
  const [page, setPage] = useState(() => filtersFromSearch((k) => searchParams.get(k)).page);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  const PAGE_SIZE = LISTINGS_PAGE_SIZE;

  // The inputs above are drafts; `applied` is what the search actually uses. Filters apply on
  // submit, except the city chips and chip removal, which apply at once.
  const [applied, setApplied] = useState<AppliedFilters>(() => filtersFromSearch((k) => searchParams.get(k)).applied);
  const apply = (overrides: Partial<AppliedFilters> = {}) => {
    setApplied({ q, city, locality, minRent, maxRent, category, configuration, furnishing, ...overrides });
    setPage(1);
  };

  const propertiesQuery = useApiQuery<PropertyDTO[]>("/properties", listingQueryParams(applied, page), { initial });
  const fetched = propertiesQuery.data ?? [];
  // In-memory sorting for marketplace ordering
  const properties =
    sortBy === "price_asc"
      ? [...fetched].sort((a, b) => Number(a.monthly_rent) - Number(b.monthly_rent))
      : sortBy === "price_desc"
        ? [...fetched].sort((a, b) => Number(b.monthly_rent) - Number(a.monthly_rent))
        : fetched;
  const totalCount =
    fetched.length >= PAGE_SIZE ? (page + 1) * PAGE_SIZE : (page - 1) * PAGE_SIZE + fetched.length;
  const isLoading = propertiesQuery.isLoading;
  const error = propertiesQuery.error ? propertiesQuery.error.message || "Failed to load properties" : null;
  const correlationId = (propertiesQuery.error as ApiError | null)?.requestId;
  const fetchProperties = propertiesQuery.refetch;

  // Keep the URL shareable. replaceState only; no React state is touched here.
  useEffect(() => {
    const url = new URL(window.location.href);
    const entries: Record<string, string | number> = {
      q: applied.q,
      city: applied.city,
      locality: applied.locality,
      min_rent: applied.minRent,
      max_rent: applied.maxRent,
      category: applied.category,
      config: applied.configuration,
      furnishing: applied.furnishing,
      sort: sortBy === "newest" ? "" : sortBy,
      page: page === 1 ? "" : page,
    };
    Object.entries(entries).forEach(([k, v]) => {
      if (v !== "") url.searchParams.set(k, String(v));
      else url.searchParams.delete(k);
    });
    window.history.replaceState(null, "", url.toString());
  }, [applied, sortBy, page]);

  const handleFilterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setMobileFiltersOpen(false);
    apply();
  };

  const handleCitySelect = (selectedCity: string) => {
    const nextCity = city === selectedCity ? "" : selectedCity;
    setCity(nextCity);
    apply({ city: nextCity });
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    apply();
  };

  const handleReset = () => {
    setQ("");
    setCity("");
    setLocality("");
    setMinRent("");
    setMaxRent("");
    setCategory("");
    setConfiguration("");
    setFurnishing("");
    setSortBy("newest");
    setApplied({ q: "", city: "", locality: "", minRent: "", maxRent: "", category: "", configuration: "", furnishing: "" });
    setPage(1);
  };

  // Chips show what is applied; removing one clears both the draft and the applied value.
  const activeFilters = [
    applied.q && { label: `Search: “${applied.q}”`, onRemove: () => { setQ(""); apply({ q: "" }); } },
    applied.city && { label: `City: ${applied.city}`, onRemove: () => { setCity(""); apply({ city: "" }); } },
    applied.minRent && { label: `Min: ${formatCurrency(applied.minRent)}`, onRemove: () => { setMinRent(""); apply({ minRent: "" }); } },
    applied.maxRent && { label: `Max: ${formatCurrency(applied.maxRent)}`, onRemove: () => { setMaxRent(""); apply({ maxRent: "" }); } },
    applied.category && { label: `Category: ${applied.category}`, onRemove: () => { setCategory(""); apply({ category: "" }); } },
    applied.configuration && { label: `Type: ${applied.configuration}`, onRemove: () => { setConfiguration(""); apply({ configuration: "" }); } },
  ].filter(Boolean) as { label: string; onRemove: () => void }[];

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      <CityDatalist id="city-suggestions" cities={cities} />
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
              <option value="newest">{applied.q ? "Best match" : "Newest First"}</option>
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

      {/* Free-text search: describe the place in your own words */}
      <form onSubmit={handleSearchSubmit} role="search" className="flex gap-2">
        <label htmlFor="property-search" className="sr-only">Describe what you&apos;re looking for</label>
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-charcoal-muted absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
          <input
            id="property-search"
            type="search"
            value={q}
            maxLength={300}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Describe it: quiet furnished room near Indiranagar metro, pets OK"
            className="w-full min-h-[44px] pl-9 pr-3 rounded-xl border border-warm-200 bg-white text-base sm:text-sm text-charcoal placeholder:text-charcoal-muted focus:outline-none focus:ring-2 focus:ring-forest/40"
          />
        </div>
        <Button type="submit" variant="primary" className="min-h-[44px] shrink-0">Search</Button>
      </form>

      {/* Desktop Filter Form */}
      <form
        onSubmit={handleFilterSubmit}
        className="hidden md:block bg-white p-5 rounded-2xl border border-warm-200 shadow-xs space-y-4"
      >
        {/* Popular Cities */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-semibold text-charcoal-muted mr-1">Popular:</span>
          {popularCities(cities).map((c) => (
            <button
              key={c.slug}
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
              list="city-suggestions"
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
              list="city-suggestions"
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
          onRetry={fetchProperties}
        />
      )}

      {/* Results Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <Skeleton key={n} variant="card" />
          ))}
        </div>
      ) : error ? null : properties.length === 0 ? (
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
            {properties.map((prop, i) => (
              <PropertyCard key={prop.id} property={prop} priority={i === 0} />
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

export function PropertiesBrowser({ initial }: { initial?: InitialListings }) {
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
      <PropertiesListContent initial={initial} />
    </Suspense>
  );
}
