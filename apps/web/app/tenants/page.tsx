"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useApiQuery } from "@/hooks/useApiQuery";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api-client";
import { ExistingTenantVacancyDTO, TenantMembershipDTO } from "@flatmate/contracts";
import { Card, Button, Input, Badge, Modal, EmptyState, ErrorState } from "@flatmate/ui";
import { formatCurrency, formatDate } from "@/lib/utils";
import { InlineNotice } from "@/components/states/InlineNotice";
import {
  Users,
  Plus,
  Home,
  Calendar,
  CheckCircle2,
  Clock,
  Sparkles,
  MapPin,
  FileText,
  AlertCircle,
  XCircle,
  Trash2,
} from "lucide-react";

export default function TenantsVacancyPage() {
  const { isAuthenticated, isLoading: authLoading, user } = useAuth();
  const router = useRouter();
  const vacanciesQuery = useApiQuery<ExistingTenantVacancyDTO[]>(authLoading ? null : "/tenants/vacancies");
  const membershipsQuery = useApiQuery<TenantMembershipDTO[]>(isAuthenticated ? "/tenants/my-memberships" : null);
  const vacancies = vacanciesQuery.data ?? [];
  const memberships = membershipsQuery.data ?? [];
  const isLoading = authLoading || vacanciesQuery.isLoading;
  const loadData = () => {
    vacanciesQuery.refetch();
    membershipsQuery.refetch();
  };
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // Filter State
  const [filterGender, setFilterGender] = useState<string>("all");

  // Form State
  // A vacancy belongs to one of the tenant's own leases; default to the first until they pick one.
  const [pickedMembershipId, setSelectedMembershipId] = useState("");
  const selectedMembership = memberships.find((m) => m.id === pickedMembershipId) ?? memberships[0] ?? null;
  const [formError, setFormError] = useState<string | null>(null);
  const openVacancyForm = () => {
    setFormError(null);
    setIsModalOpen(true);
  };
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [expectedRent, setExpectedRent] = useState("12000");
  const [depositRequired, setDepositRequired] = useState("30000");
  const [preferredGender, setPreferredGender] = useState("any");
  const [vacantFrom, setVacantFrom] = useState(new Date().toISOString().split("T")[0]);
  const [isSubmitting, setIsSubmitting] = useState(false);


  const handleCreateVacancy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMembership) {
      setFormError("You need an active tenancy on Flatmate to post a replacement vacancy.");
      return;
    }
    setFormError(null);
    try {
      setIsSubmitting(true);
      await apiClient("/tenants/vacancies", {
        method: "POST",
        body: JSON.stringify({
          property_id: selectedMembership.property_id,
          // The API falls back to the lease's room when this is null.
          room_id: selectedMembership.room_id ?? undefined,
          title,
          description,
          vacant_from: vacantFrom,
          expected_rent: parseFloat(expectedRent),
          deposit_required: parseFloat(depositRequired),
          preferred_gender: preferredGender,
        }),
      });
      setIsModalOpen(false);
      setActionNotice("Roommate replacement vacancy posted successfully!");
      setTimeout(() => setActionNotice(null), 3000);
      loadData();
    } catch (err: any) {
      setFormError(err.message || "Failed to create vacancy posting");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCloseVacancy = async (vacancyId: string) => {
    try {
      await apiClient(`/tenants/vacancies/${vacancyId}`, { method: "DELETE" });
      setActionNotice("Vacancy marked as filled / closed.");
      setTimeout(() => setActionNotice(null), 3000);
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to close vacancy");
    }
  };

  const filteredVacancies = vacancies.filter((v) => {
    if (filterGender !== "all" && v.preferred_gender !== filterGender) {
      return false;
    }
    return true;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 bg-forest-pale text-forest text-xs font-semibold px-3 py-1 rounded-full mb-2">
            <Users className="w-3.5 h-3.5" />
            <span>Tenant Replacement & Vacancies</span>
          </div>
          <h1 className="text-3xl font-extrabold text-charcoal tracking-tight">
            Find a Replacement Roommate
          </h1>
          <p className="text-charcoal-muted text-sm mt-1">
            Moving out or have an empty bedroom in your flat? List your room replacement vacancy directly to verified seekers.
          </p>
        </div>

        {isAuthenticated && (
          <Button
            variant="primary"
            size="md"
            className="gap-2 shadow-sm"
            onClick={openVacancyForm}
          >
            <Plus className="w-4 h-4" />
            <span>Post a Vacancy</span>
          </Button>
        )}
      </div>

      {actionNotice && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-2xl text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Active Tenancy Memberships Banner for logged in user */}
      {isAuthenticated && memberships.length > 0 && (
        <Card className="p-5 border-forest/20 bg-forest-pale/40">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs font-bold text-forest uppercase tracking-wider block">Your Verified Tenancies</span>
              <p className="text-xs text-charcoal-muted mt-0.5">
                You have {memberships.length} active tenancy lease{memberships.length > 1 ? "s" : ""} on record.
              </p>
            </div>
            <Badge variant="forest">Active Tenant</Badge>
          </div>
        </Card>
      )}

      {/* Filter Chips */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-charcoal-muted font-semibold">Filter:</span>
        {["all", "any", "female_only", "male_only"].map((g) => (
          <button
            key={g}
            onClick={() => setFilterGender(g)}
            className={`px-3 py-1.5 rounded-full font-medium transition-colors ${
              filterGender === g
                ? "bg-forest text-white"
                : "bg-warm text-charcoal-muted hover:bg-slate-200"
            }`}
          >
            {g === "all" ? "All Genders" : g === "female_only" ? "Female Only" : g === "male_only" ? "Male Only" : "Any Gender"}
          </button>
        ))}
      </div>

      {/* Active Listings Grid */}
      <div className="space-y-4">
        <h2 className="text-xl font-bold text-charcoal">Current Roommate Vacancies</h2>

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-pulse">
            {[1, 2, 3].map((n) => (
              <div key={n} className="bg-slate-200 h-64 rounded-2xl" />
            ))}
          </div>
        ) : vacanciesQuery.error ? (
          <ErrorState title="Couldn't load vacancies" message={vacanciesQuery.error.message} onRetry={loadData} />
        ) : filteredVacancies.length === 0 ? (
          <EmptyState
            title="No active roommate vacancies"
            description="When tenants in existing leases declare upcoming vacancies, they will appear here."
            actionLabel={isAuthenticated ? "Post Vacancy" : "Sign In to Post"}
            onAction={() => (isAuthenticated ? openVacancyForm() : router.push("/login"))}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredVacancies.map((v) => {
              const isOwnerOfVacancy = user && (v as any).posted_by_tenant_id === user.id;

              return (
                <Card key={v.id} className="p-6 border-slate-200/80 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <Badge variant="default" className="uppercase text-[10px] tracking-wider">
                        Gender: {v.preferred_gender.replace(/_/g, " ")}
                      </Badge>
                      <span className="text-xs text-charcoal-muted">Available {formatDate(v.vacant_from)}</span>
                    </div>
                    <h3 className="font-bold text-charcoal text-base mb-1">{v.title}</h3>
                    <p className="text-xs text-charcoal-muted line-clamp-3 mb-4">{v.description}</p>
                  </div>

                  <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                    <div>
                      <span className="text-[11px] text-charcoal-muted uppercase font-semibold">Monthly Share</span>
                      <div className="text-lg font-bold text-charcoal">
                        {formatCurrency(v.expected_rent, "INR")}
                        <span className="text-xs font-normal text-charcoal-muted">/mo</span>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {isOwnerOfVacancy && (
                        <button
                          type="button"
                          onClick={() => handleCloseVacancy(v.id)}
                          className="text-xs text-rose-600 hover:underline flex items-center gap-1"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          <span>Close</span>
                        </button>
                      )}
                      <Link href={`/properties/${v.property_id}`}>
                        <Button size="sm" variant="outline">
                          View Flat
                        </Button>
                      </Link>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Post Vacancy Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Post Roommate Replacement Vacancy"
        description="Share details about the room opening in your apartment."
      >
        <form onSubmit={handleCreateVacancy} className="space-y-4 mt-2">
          {formError && <InlineNotice tone="error">{formError}</InlineNotice>}
          {memberships.length > 0 ? (
            <div>
              <label htmlFor="vacancy-lease" className="block text-xs font-semibold text-charcoal mb-1">Your tenancy</label>
              <select
                id="vacancy-lease"
                value={selectedMembership?.id ?? ""}
                onChange={(e) => setSelectedMembershipId(e.target.value)}
                required
                className="w-full min-h-[44px] text-xs rounded-xl border border-slate-200 p-2.5 bg-white"
              >
                {memberships.map((m) => (
                  <option key={m.id} value={m.id}>
                    Property #{m.property_id.slice(0, 8)} (Rent: ₹{m.monthly_rent})
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <InlineNotice tone="error">
              Only tenants with an active lease on Flatmate can post a replacement vacancy.
            </InlineNotice>
          )}

          <Input
            label="Vacancy Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Master Bedroom available in 3BHK HSR Layout"
            required
          />

          <div>
            <label className="block text-xs font-semibold text-charcoal mb-1">Description & House Rules</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              required
              className="w-full rounded-xl border border-slate-200 p-2.5 text-xs focus:ring-2 focus:ring-forest focus:outline-none"
              placeholder="Private attached bathroom, fully furnished with AC, shared kitchen and living room..."
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Expected Monthly Rent (₹)"
              type="number"
              value={expectedRent}
              onChange={(e) => setExpectedRent(e.target.value)}
              required
            />
            <Input
              label="Security Deposit (₹)"
              type="number"
              value={depositRequired}
              onChange={(e) => setDepositRequired(e.target.value)}
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1">Preferred Gender</label>
              <select
                value={preferredGender}
                onChange={(e) => setPreferredGender(e.target.value)}
                className="w-full text-xs rounded-xl border border-slate-200 p-2.5 bg-white"
              >
                <option value="any">Any / Open</option>
                <option value="female_only">Female Only</option>
                <option value="male_only">Male Only</option>
              </select>
            </div>
            <Input
              label="Vacant From Date"
              type="date"
              value={vacantFrom}
              onChange={(e) => setVacantFrom(e.target.value)}
              required
            />
          </div>

          <Button
            type="submit"
            variant="primary"
            className="w-full mt-2 min-h-[44px]"
            isLoading={isSubmitting}
            disabled={!selectedMembership}
          >
            Post Vacancy
          </Button>
        </form>
      </Modal>
    </div>
  );
}
