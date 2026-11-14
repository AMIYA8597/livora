"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api-client";
import {
  ApplicationDTO, ProfileDTO, Lifestyle10DimensionDTO, DealbreakerDTO,
  AppointmentDTO, UserTrustStatusDTO, PrivacySettingsDTO, PropertyDTO
} from "@flatmate/contracts";
import { Card, Button, Input, Badge, Avatar, Modal, EmptyState } from "@flatmate/ui";
import { formatCurrency, formatDate, formatDateTimeIST, formatIndianCompactCurrency } from "@/lib/utils";
import {
  LayoutDashboard, FileText, CheckCircle2, Clock, XCircle, ShieldCheck,
  Sparkles, Calendar, User, Shield, Heart, Trash2, MapPin, AlertCircle,
  Eye, Building, Check, X
} from "lucide-react";

export default function DashboardPage() {
  const { user, isAuthenticated, isOwner, isAdmin, isPgOperator } = useAuth();

  // Tab State
  const [activeTab, setActiveTab] = useState<
    "applications" | "appointments" | "saved" | "profile" | "quiz" | "dealbreakers"
  >("applications");

  // Core Data States
  const [applications, setApplications] = useState<ApplicationDTO[]>([]);
  const [appointments, setAppointments] = useState<AppointmentDTO[]>([]);
  const [savedProperties, setSavedProperties] = useState<PropertyDTO[]>([]);
  const [profile, setProfile] = useState<ProfileDTO | null>(null);
  const [privacy, setPrivacy] = useState<PrivacySettingsDTO | null>(null);
  const [trustStatus, setTrustStatus] = useState<UserTrustStatusDTO | null>(null);
  const [dealbreakers, setDealbreakers] = useState<DealbreakerDTO[]>([]);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Verification Modal State
  const [isVerifyModalOpen, setIsVerifyModalOpen] = useState(false);
  const [verifyType, setVerifyType] = useState("government_id");
  const [verifyDocUrl, setVerifyDocUrl] = useState("");
  const [isSubmittingVerify, setIsSubmittingVerify] = useState(false);
  const [verifySuccess, setVerifySuccess] = useState(false);

  // Profile Edit State
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [occupation, setOccupation] = useState("");
  const [budgetMin, setBudgetMin] = useState("10000");
  const [budgetMax, setBudgetMax] = useState("25000");
  const [preferredLocations, setPreferredLocations] = useState("");
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  // Lifestyle 10-Dimension Form State
  const [sleepSchedule, setSleepSchedule] = useState("early_bird");
  const [cleanliness, setCleanliness] = useState(4);
  const [workArrangement, setWorkArrangement] = useState("hybrid");
  const [diet, setDiet] = useState("pure_veg");
  const [smoking, setSmoking] = useState("never");
  const [pets, setPets] = useState("cats_and_dogs_ok");
  const [socialBattery, setSocialBattery] = useState("balanced");
  const [noiseTolerance, setNoiseTolerance] = useState("moderate");
  const [guestsPolicy, setGuestsPolicy] = useState("occasional_weekends");
  const [isSavingQuiz, setIsSavingQuiz] = useState(false);

  // Dealbreaker Form State
  const [dealbreakerRule, setDealbreakerRule] = useState("no_smoking_inside");
  const [dealbreakerValue, setDealbreakerValue] = useState("never");
  const [isStrictDealbreaker, setIsStrictDealbreaker] = useState(true);
  const [isAddingDealbreaker, setIsAddingDealbreaker] = useState(false);

  // 1. Load Initial Core Data
  const loadDashboardData = async () => {
    if (!isAuthenticated) return;
    try {
      setIsLoading(true);
      const [appsData, aptsData, profileData, privacyData, trustData, dbsData] = await Promise.all([
        apiClient<ApplicationDTO[]>("/applications/me").catch(() => []),
        apiClient<AppointmentDTO[]>("/appointments/").catch(() => []),
        apiClient<ProfileDTO>("/profiles/me").catch(() => null),
        apiClient<PrivacySettingsDTO>("/profiles/me/privacy").catch(() => null),
        apiClient<UserTrustStatusDTO>("/verification/status").catch(() => null),
        apiClient<DealbreakerDTO[]>("/lifestyle/dealbreakers").catch(() => []),
      ]);

      setApplications(appsData || []);
      setAppointments(aptsData || []);
      setProfile(profileData);
      setPrivacy(privacyData);
      setTrustStatus(trustData);
      setDealbreakers(dbsData || []);

      if (profileData) {
        setDisplayName(profileData.display_name || "");
        setBio(profileData.bio || "");
        setOccupation(profileData.occupation || profileData.designation || "");
        setBudgetMin(String(profileData.budget_min || 10000));
        setBudgetMax(String(profileData.budget_max || 25000));
        setPreferredLocations((profileData.preferred_locations || []).join(", "));

        if (profileData.lifestyle_traits) {
          const t = profileData.lifestyle_traits;
          if (t.sleep_schedule) setSleepSchedule(t.sleep_schedule);
          if (t.cleanliness_level) setCleanliness(Number(t.cleanliness_level));
          if (t.work_arrangement) setWorkArrangement(t.work_arrangement);
          if (t.diet || t.diet_preference) setDiet(t.diet_preference || t.diet || "pure_veg");
          if (t.smoking) setSmoking(t.smoking);
          if (t.pets || t.pet_preference) setPets(t.pet_preference || t.pets || "cats_and_dogs_ok");
          if (t.social_battery) setSocialBattery(t.social_battery);
          if (t.noise_tolerance) setNoiseTolerance(t.noise_tolerance);
          if (t.guests_policy) setGuestsPolicy(t.guests_policy);
        }
      }
    } catch (err) {
      console.error("Dashboard core load error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  // Load Saved Properties from localStorage
  const loadSavedProperties = async () => {
    try {
      const raw = localStorage.getItem("flatmate_saved_properties");
      if (!raw) {
        setSavedProperties([]);
        return;
      }
      const ids: string[] = JSON.parse(raw);
      if (!Array.isArray(ids) || ids.length === 0) {
        setSavedProperties([]);
        return;
      }
      const propPromises = ids.map((id) =>
        apiClient<PropertyDTO>(`/properties/${id}`).catch(() => null)
      );
      const results = await Promise.all(propPromises);
      setSavedProperties(results.filter((p): p is PropertyDTO => p !== null));
    } catch (err) {
      console.error("Failed to load saved properties:", err);
      setSavedProperties([]);
    }
  };

  useEffect(() => {
    if (activeTab === "saved") {
      loadSavedProperties();
    }
  }, [activeTab]);

  const handleRemoveSavedProperty = (propertyId: string) => {
    try {
      const raw = localStorage.getItem("flatmate_saved_properties");
      if (raw) {
        const ids: string[] = JSON.parse(raw);
        const filtered = ids.filter((id) => id !== propertyId);
        localStorage.setItem("flatmate_saved_properties", JSON.stringify(filtered));
      }
      setSavedProperties((prev) => prev.filter((p) => p.id !== propertyId));
      setActionNotice("Property removed from saved list.");
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err) {
      console.error("Failed to remove saved property:", err);
    }
  };

  // Withdraw Application
  const handleWithdrawApplication = async (appId: string) => {
    try {
      await apiClient(`/applications/${appId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: "withdrawn" }),
      });
      setApplications((prev) =>
        prev.map((a) => (a.id === appId ? { ...a, status: "withdrawn" } : a))
      );
      setActionNotice("Application withdrawn successfully.");
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to withdraw application");
    }
  };

  // Cancel Appointment
  const handleCancelAppointment = async (aptId: string) => {
    try {
      await apiClient(`/appointments/${aptId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: "cancelled", cancellation_reason: "Cancelled by applicant" }),
      });
      setAppointments((prev) =>
        prev.map((a) => (a.id === aptId ? { ...a, status: "cancelled" } : a))
      );
      setActionNotice("Viewing appointment cancelled.");
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to cancel appointment");
    }
  };

  // Profile Save
  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingProfile(true);
    try {
      const locList = preferredLocations
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      const updated = await apiClient<ProfileDTO>("/profiles/me", {
        method: "PUT",
        body: JSON.stringify({
          display_name: displayName,
          bio,
          occupation,
          budget_min: parseInt(budgetMin, 10),
          budget_max: parseInt(budgetMax, 10),
          preferred_locations: locList,
        }),
      });
      setProfile(updated);
      setActionNotice("Profile details updated successfully.");
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to update profile");
    } finally {
      setIsSavingProfile(false);
    }
  };

  // Lifestyle Quiz Save
  const handleSaveQuiz = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingQuiz(true);
    try {
      const payload: Lifestyle10DimensionDTO = {
        sleep_schedule: sleepSchedule,
        cleanliness_level: cleanliness,
        work_arrangement: workArrangement,
        diet_preference: diet,
        smoking: smoking,
        pet_preference: pets,
        social_battery: socialBattery,
        noise_tolerance: noiseTolerance,
        guests_policy: guestsPolicy,
      };

      await apiClient("/lifestyle/me", {
        method: "PUT",
        body: JSON.stringify(payload),
      });

      setActionNotice("Compatibility matrix and preferences saved.");
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to update lifestyle preferences");
    } finally {
      setIsSavingQuiz(false);
    }
  };

  // Dealbreaker Add
  const handleAddDealbreaker = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsAddingDealbreaker(true);
      const created = await apiClient<DealbreakerDTO>("/lifestyle/dealbreakers", {
        method: "POST",
        body: JSON.stringify({
          rule_key: dealbreakerRule,
          is_strict: isStrictDealbreaker,
          expected_value: dealbreakerValue,
        }),
      });
      setDealbreakers((prev) => [...prev, created]);
      setActionNotice("Dealbreaker rule added.");
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to add dealbreaker");
    } finally {
      setIsAddingDealbreaker(false);
    }
  };

  // Dealbreaker Delete
  const handleDeleteDealbreaker = async (id: string) => {
    try {
      await apiClient(`/lifestyle/dealbreakers/${id}`, { method: "DELETE" });
      setDealbreakers((prev) => prev.filter((d) => d.id !== id));
      setActionNotice("Dealbreaker rule removed.");
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to delete dealbreaker");
    }
  };

  // Verification Submit
  const handleVerifySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsSubmittingVerify(true);
      await apiClient("/verification/submit", {
        method: "POST",
        body: JSON.stringify({
          verification_type: verifyType,
          document_url: verifyDocUrl || "https://documents.flatmate.platform/v/doc_sample.pdf",
        }),
      });
      setVerifySuccess(true);
      const freshTrust = await apiClient<UserTrustStatusDTO>("/verification/status").catch(() => null);
      if (freshTrust) setTrustStatus(freshTrust);
      setTimeout(() => {
        setIsVerifyModalOpen(false);
        setVerifySuccess(false);
      }, 2000);
    } catch (err: any) {
      alert(err.message || "Failed to submit verification");
    } finally {
      setIsSubmittingVerify(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto py-20 px-4 text-center">
        <Card className="p-8">
          <LayoutDashboard className="w-12 h-12 text-forest mx-auto mb-3" />
          <h2 className="text-xl font-bold text-charcoal mb-2">Sign in to My Space</h2>
          <p className="text-xs text-charcoal-muted mb-6">Manage your applications, visits, and saved homes.</p>
          <Button variant="primary" onClick={() => (window.location.href = "/login")} className="w-full">
            Sign In
          </Button>
        </Card>
      </div>
    );
  }

  const trustScore = trustStatus ? trustStatus.total_trust_score : 20;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header Profile Bar */}
      <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center space-x-4">
          <Avatar alt={user?.full_name || "User"} size="lg" isVerified={trustStatus?.is_fully_verified} />
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-2xl font-bold text-charcoal">{user?.full_name}</h1>
              <span className="text-xs uppercase font-bold text-forest bg-forest-pale px-2.5 py-0.5 rounded-full">
                {user?.role}
              </span>
            </div>
            <p className="text-xs text-charcoal-muted mt-0.5">{user?.email}</p>
          </div>
        </div>

        {/* Real Trust Score Box */}
        <div className="flex items-center space-x-3 bg-forest-pale/60 border border-forest/20 px-4 py-2.5 rounded-2xl text-forest text-xs">
          <ShieldCheck className="w-5 h-5 text-forest shrink-0" />
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold">Trust Score: {trustScore}/100</span>
              <button
                onClick={() => setIsVerifyModalOpen(true)}
                className="text-[11px] font-semibold text-forest underline hover:text-forest-secondary"
              >
                + Verify ID
              </button>
            </div>
            <span className="text-forest/80 text-[11px]">
              {trustStatus?.badges && trustStatus.badges.length > 0
                ? trustStatus.badges.join(" • ")
                : "Standard User • ID Unverified"}
            </span>
          </div>
        </div>
      </div>

      {actionNotice && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-2xl text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex space-x-2 border-b border-slate-200 overflow-x-auto pb-1">
        <button
          onClick={() => setActiveTab("applications")}
          className={`pb-3 px-3 text-xs sm:text-sm font-semibold border-b-2 whitespace-nowrap transition-colors ${
            activeTab === "applications"
              ? "border-forest text-forest font-bold"
              : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          My Applications ({applications.length})
        </button>

        <button
          onClick={() => setActiveTab("appointments")}
          className={`pb-3 px-3 text-xs sm:text-sm font-semibold border-b-2 whitespace-nowrap transition-colors ${
            activeTab === "appointments"
              ? "border-forest text-forest font-bold"
              : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          Scheduled Visits ({appointments.length})
        </button>

        <button
          onClick={() => setActiveTab("saved")}
          className={`pb-3 px-3 text-xs sm:text-sm font-semibold border-b-2 whitespace-nowrap transition-colors flex items-center space-x-1 ${
            activeTab === "saved"
              ? "border-forest text-forest font-bold"
              : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          <Heart className="w-3.5 h-3.5" />
          <span>Saved Places</span>
        </button>

        <button
          onClick={() => setActiveTab("profile")}
          className={`pb-3 px-3 text-xs sm:text-sm font-semibold border-b-2 whitespace-nowrap transition-colors flex items-center space-x-1 ${
            activeTab === "profile"
              ? "border-forest text-forest font-bold"
              : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          <User className="w-3.5 h-3.5" />
          <span>Profile</span>
        </button>

        <button
          onClick={() => setActiveTab("quiz")}
          className={`pb-3 px-3 text-xs sm:text-sm font-semibold border-b-2 whitespace-nowrap transition-colors flex items-center space-x-1 ${
            activeTab === "quiz"
              ? "border-forest text-forest font-bold"
              : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>10D Matrix</span>
        </button>

        <button
          onClick={() => setActiveTab("dealbreakers")}
          className={`pb-3 px-3 text-xs sm:text-sm font-semibold border-b-2 whitespace-nowrap transition-colors flex items-center space-x-1 ${
            activeTab === "dealbreakers"
              ? "border-forest text-forest font-bold"
              : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          <Shield className="w-3.5 h-3.5" />
          <span>Dealbreakers ({dealbreakers.length})</span>
        </button>
      </div>

      {/* 1. Tab: Rental Applications */}
      {activeTab === "applications" && (
        <div className="space-y-4">
          {applications.length === 0 ? (
            <EmptyState
              title="No applications submitted yet"
              description="Explore flats or private rooms and submit an introduction to the landlord or roommates."
              actionLabel="Discover Properties"
              onAction={() => (window.location.href = "/properties")}
            />
          ) : (
            applications.map((app) => (
              <Card key={app.id} className="p-5 border-slate-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs text-charcoal-muted font-mono">App #{app.id.slice(0, 8)}</span>
                    <Badge
                      variant={
                        app.status === "accepted" || app.status === "approved"
                          ? "success"
                          : app.status === "rejected" || app.status === "withdrawn"
                          ? "danger"
                          : "warning"
                      }
                      size="sm"
                      className="capitalize"
                    >
                      {app.status}
                    </Badge>
                  </div>
                  <h4 className="font-semibold text-charcoal text-base mt-1">
                    Offered Rent: {formatCurrency(app.proposed_rent, "INR")}/mo
                  </h4>
                  <p className="text-xs text-charcoal-muted mt-1">
                    Target Move-In: {formatDate(app.move_in_target)} • Submitted: {formatDate(app.submitted_at)}
                  </p>
                  <p className="text-xs text-charcoal mt-2 italic bg-warm p-2.5 rounded-lg border border-slate-100">
                    &ldquo;{app.introduction}&rdquo;
                  </p>
                </div>

                <div className="flex items-center space-x-2 self-end sm:self-center">
                  {(app.status === "submitted" || app.status === "reviewing" || app.status === "under_review") && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-rose-600 border-rose-200 hover:bg-rose-50"
                      onClick={() => handleWithdrawApplication(app.id)}
                    >
                      Withdraw
                    </Button>
                  )}
                  <Link href={`/properties/${app.property_id}`}>
                    <Button size="sm" variant="ghost">
                      View Listing
                    </Button>
                  </Link>
                </div>
              </Card>
            ))
          )}
        </div>
      )}

      {/* 2. Tab: Appointments */}
      {activeTab === "appointments" && (
        <div className="space-y-4">
          {appointments.length === 0 ? (
            <EmptyState
              title="No viewing appointments booked"
              description="Open any listing to schedule a physical walkthrough or virtual inspection."
              actionLabel="Find Places to Visit"
              onAction={() => (window.location.href = "/properties")}
            />
          ) : (
            appointments.map((apt) => (
              <Card key={apt.id} className="p-5 border-slate-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center space-x-2">
                    <Badge variant={apt.appointment_type === "physical_visit" ? "default" : "forest"} size="sm">
                      {apt.appointment_type === "physical_visit" ? "Physical Walkthrough" : "Video Inspection"}
                    </Badge>
                    <Badge
                      variant={
                        apt.status === "confirmed"
                          ? "success"
                          : apt.status === "cancelled"
                          ? "danger"
                          : "warning"
                      }
                      size="sm"
                      className="capitalize"
                    >
                      {apt.status}
                    </Badge>
                  </div>
                  <h4 className="font-semibold text-charcoal text-base mt-1.5 flex items-center gap-1.5">
                    <Clock className="w-4 h-4 text-forest" />
                    <span>Scheduled: {formatDateTimeIST(apt.scheduled_at)}</span>
                  </h4>
                  {apt.notes && (
                    <p className="text-xs text-charcoal-muted mt-1">Notes: {apt.notes}</p>
                  )}
                </div>

                <div className="flex items-center space-x-2 self-end sm:self-center">
                  {apt.status !== "cancelled" && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-rose-600 border-rose-200 hover:bg-rose-50"
                      onClick={() => handleCancelAppointment(apt.id)}
                    >
                      Cancel Visit
                    </Button>
                  )}
                </div>
              </Card>
            ))
          )}
        </div>
      )}

      {/* 3. Tab: Saved Properties */}
      {activeTab === "saved" && (
        <div className="space-y-4">
          {savedProperties.length === 0 ? (
            <EmptyState
              title="No saved properties yet"
              description="Click the heart icon on any accommodation card to bookmark it for later."
              actionLabel="Discover Properties"
              onAction={() => (window.location.href = "/properties")}
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {savedProperties.map((prop) => (
                <Card key={prop.id} className="p-5 border-slate-200/80 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <Badge variant="forest">{prop.configuration}</Badge>
                      <button
                        type="button"
                        onClick={() => handleRemoveSavedProperty(prop.id)}
                        className="text-xs text-rose-500 hover:text-rose-700 flex items-center gap-1"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>Remove</span>
                      </button>
                    </div>
                    <h3 className="font-bold text-charcoal text-base mb-1">{prop.title}</h3>
                    <p className="text-xs text-charcoal-muted flex items-center gap-1 mb-3">
                      <MapPin className="w-3.5 h-3.5 text-forest" />
                      <span>{prop.address_display}, {prop.city}</span>
                    </p>
                    <div className="text-lg font-bold text-charcoal">
                      {formatCurrency(prop.monthly_rent, "INR")}
                      <span className="text-xs font-normal text-charcoal-muted">/mo</span>
                    </div>
                  </div>

                  <div className="pt-4 border-t border-slate-100 flex items-center justify-between mt-3">
                    <span className="text-xs text-charcoal-muted">Deposit: {formatCurrency(prop.security_deposit, "INR")}</span>
                    <Link href={`/properties/${prop.id}`}>
                      <Button size="sm" variant="primary">
                        View Details
                      </Button>
                    </Link>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 4. Tab: Profile Editing */}
      {activeTab === "profile" && (
        <Card className="p-8 border-slate-200/80 max-w-2xl">
          <div className="mb-6">
            <h2 className="text-xl font-bold text-charcoal">Edit Public Profile</h2>
            <p className="text-xs text-charcoal-muted mt-1">
              Your profile information is visible to potential roommates and landlords in search directories.
            </p>
          </div>

          <form onSubmit={handleSaveProfile} className="space-y-4">
            <Input
              label="Display Name"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />

            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1">About Me / Bio</label>
              <textarea
                rows={3}
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                placeholder="Share a bit about your work, routine, and roommate vibe..."
                className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-forest"
              />
            </div>

            <Input
              label="Occupation / Designation"
              value={occupation}
              onChange={(e) => setOccupation(e.target.value)}
              placeholder="e.g. Senior Software Engineer"
            />

            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Min Monthly Budget (₹)"
                type="number"
                value={budgetMin}
                onChange={(e) => setBudgetMin(e.target.value)}
              />
              <Input
                label="Max Monthly Budget (₹)"
                type="number"
                value={budgetMax}
                onChange={(e) => setBudgetMax(e.target.value)}
              />
            </div>

            <Input
              label="Preferred Localities (comma separated)"
              value={preferredLocations}
              onChange={(e) => setPreferredLocations(e.target.value)}
              placeholder="e.g. Koramangala, Indiranagar, HSR Layout"
            />

            <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isSavingProfile}>
              Save Profile Changes
            </Button>
          </form>
        </Card>
      )}

      {/* 5. Tab: 10D Lifestyle Quiz */}
      {activeTab === "quiz" && (
        <Card className="p-8 border-slate-200/80 max-w-3xl">
          <div className="mb-6">
            <h2 className="text-xl font-bold text-charcoal">10-Dimension Lifestyle Matrix</h2>
            <p className="text-xs text-charcoal-muted mt-1">
              Deterministic scoring and 64-dimensional pgvector embeddings calculate pairwise synergy and dealbreakers.
            </p>
          </div>

          <form onSubmit={handleSaveQuiz} className="space-y-6">
            {/* Sleep Schedule */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-charcoal-muted mb-2">
                1. Daily Sleep Schedule
              </label>
              <div className="grid grid-cols-3 gap-2">
                {["early_bird", "night_owl", "flexible"].map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setSleepSchedule(s)}
                    className={`py-2.5 px-3 rounded-xl border text-xs font-semibold capitalize text-center transition-all ${
                      sleepSchedule === s
                        ? "bg-forest-pale border-forest text-forest shadow-2xs"
                        : "border-slate-200 text-charcoal-muted hover:bg-slate-50"
                    }`}
                  >
                    {s.replace(/_/g, " ")}
                  </button>
                ))}
              </div>
            </div>

            {/* Cleanliness */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-xs font-bold uppercase tracking-wider text-charcoal-muted">
                  2. Cleanliness Standard
                </label>
                <span className="text-xs font-bold text-forest">{cleanliness} / 5</span>
              </div>
              <input
                type="range"
                min="1"
                max="5"
                step="1"
                value={cleanliness}
                onChange={(e) => setCleanliness(parseInt(e.target.value, 10))}
                className="w-full accent-forest"
              />
              <div className="flex justify-between text-[11px] text-charcoal-muted mt-1">
                <span>1 - Relaxed</span>
                <span>3 - Moderate</span>
                <span>5 - Spotless</span>
              </div>
            </div>

            {/* Work Routine */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-charcoal-muted mb-2">
                3. Work Routine
              </label>
              <div className="grid grid-cols-3 gap-2">
                {["remote", "hybrid", "on_site"].map((w) => (
                  <button
                    key={w}
                    type="button"
                    onClick={() => setWorkArrangement(w)}
                    className={`py-2.5 px-3 rounded-xl border text-xs font-semibold capitalize text-center transition-all ${
                      workArrangement === w
                        ? "bg-forest-pale border-forest text-forest shadow-2xs"
                        : "border-slate-200 text-charcoal-muted hover:bg-slate-50"
                    }`}
                  >
                    {w.replace(/_/g, " ")}
                  </button>
                ))}
              </div>
            </div>

            {/* Diet */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-charcoal-muted mb-2">
                4. Kitchen & Dietary Preference
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {["pure_veg", "eggetarian", "non_veg", "vegan"].map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setDiet(d)}
                    className={`py-2 px-3 rounded-xl border text-xs font-semibold capitalize text-center transition-all ${
                      diet === d
                        ? "bg-forest-pale border-forest text-forest shadow-2xs"
                        : "border-slate-200 text-charcoal-muted hover:bg-slate-50"
                    }`}
                  >
                    {d.replace(/_/g, " ")}
                  </button>
                ))}
              </div>
            </div>

            {/* Smoking */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-charcoal-muted mb-2">
                5. Smoking Policy
              </label>
              <div className="grid grid-cols-3 gap-2">
                {["never", "outside_only", "permitted"].map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setSmoking(s)}
                    className={`py-2 px-3 rounded-xl border text-xs font-semibold capitalize text-center transition-all ${
                      smoking === s
                        ? "bg-forest-pale border-forest text-forest shadow-2xs"
                        : "border-slate-200 text-charcoal-muted hover:bg-slate-50"
                    }`}
                  >
                    {s.replace(/_/g, " ")}
                  </button>
                ))}
              </div>
            </div>

            {/* Pets */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-charcoal-muted mb-2">
                6. Pet Tolerance & Allergies
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {["no_pets", "cats_ok", "dogs_ok", "allergic"].map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPets(p)}
                    className={`py-2 px-3 rounded-xl border text-xs font-semibold capitalize text-center transition-all ${
                      pets === p
                        ? "bg-forest-pale border-forest text-forest shadow-2xs"
                        : "border-slate-200 text-charcoal-muted hover:bg-slate-50"
                    }`}
                  >
                    {p.replace(/_/g, " ")}
                  </button>
                ))}
              </div>
            </div>

            <Button type="submit" variant="primary" className="w-full" isLoading={isSavingQuiz}>
              Recalculate & Save Compatibility Vector
            </Button>
          </form>
        </Card>
      )}

      {/* 6. Tab: Dealbreaker Rules */}
      {activeTab === "dealbreakers" && (
        <div className="space-y-6 max-w-3xl">
          <Card className="p-6 border-slate-200/80">
            <h3 className="font-bold text-charcoal text-lg mb-1">Enforce Non-Negotiable Dealbreakers</h3>
            <p className="text-xs text-charcoal-muted mb-4">
              Violations instantly cap pairwise match scores and trigger strict safety alerts.
            </p>

            <form onSubmit={handleAddDealbreaker} className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-charcoal-muted uppercase mb-1">
                    Rule Category
                  </label>
                  <select
                    value={dealbreakerRule}
                    onChange={(e) => setDealbreakerRule(e.target.value)}
                    className="w-full text-xs font-semibold border border-slate-300 rounded-xl p-2.5 bg-white"
                  >
                    <option value="no_smoking_inside">Strictly Smoke-Free</option>
                    <option value="pure_veg_kitchen_only">Pure Veg Kitchen Only</option>
                    <option value="no_pets_allowed">No Pets Household</option>
                    <option value="quiet_after_11pm">Quiet Hours After 11pm</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-charcoal-muted uppercase mb-1">
                    Required Value
                  </label>
                  <Input
                    value={dealbreakerValue}
                    onChange={(e) => setDealbreakerValue(e.target.value)}
                    placeholder="e.g. never, pure_veg"
                  />
                </div>

                <div className="flex items-end">
                  <Button type="submit" variant="primary" size="sm" className="w-full py-2.5" isLoading={isAddingDealbreaker}>
                    Add Rule
                  </Button>
                </div>
              </div>
            </form>
          </Card>

          <div className="space-y-2">
            <h4 className="text-xs font-bold text-charcoal-muted uppercase">Active Dealbreaker Policies ({dealbreakers.length})</h4>
            {dealbreakers.length === 0 ? (
              <p className="text-xs text-charcoal-muted italic">No dealbreakers currently active.</p>
            ) : (
              dealbreakers.map((d) => (
                <div
                  key={d.id}
                  className="p-3.5 bg-white rounded-xl border border-slate-200/80 flex items-center justify-between shadow-2xs"
                >
                  <div className="flex items-center space-x-2">
                    <Shield className="w-4 h-4 text-rose-500" />
                    <span className="text-xs font-semibold text-charcoal capitalize">
                      {d.rule_key.replace(/_/g, " ")}
                    </span>
                    <Badge variant="danger" size="sm">Strict</Badge>
                  </div>

                  <button
                    onClick={() => handleDeleteDealbreaker(d.id)}
                    className="p-1 text-slate-400 hover:text-rose-600 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Verification Submission Modal */}
      <Modal
        isOpen={isVerifyModalOpen}
        onClose={() => setIsVerifyModalOpen(false)}
        title="Submit Trust Verification Document"
        description="Verify your identity or university/employment credentials to unlock higher trust scores."
      >
        {verifySuccess ? (
          <div className="text-center py-6">
            <CheckCircle2 className="w-12 h-12 text-forest mx-auto mb-2" />
            <h4 className="font-bold text-charcoal text-base">Verification Submitted</h4>
            <p className="text-xs text-charcoal-muted mt-1">Our verification team is reviewing your document.</p>
          </div>
        ) : (
          <form onSubmit={handleVerifySubmit} className="space-y-4 mt-2">
            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1">Verification Type</label>
              <select
                value={verifyType}
                onChange={(e) => setVerifyType(e.target.value)}
                className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white text-charcoal"
              >
                <option value="government_id">Government ID (Aadhaar / Passport / DL)</option>
                <option value="student_email">University / Student ID</option>
                <option value="work_email">Corporate Work Email</option>
                <option value="background_check">Background Check Dossier</option>
              </select>
            </div>

            <Input
              label="Document Evidence URL / Reference"
              value={verifyDocUrl}
              onChange={(e) => setVerifyDocUrl(e.target.value)}
              placeholder="e.g. https://storage.flatmate.platform/v/aadhaar_masked.pdf"
            />

            <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isSubmittingVerify}>
              Submit for Verification
            </Button>
          </form>
        )}
      </Modal>
    </div>
  );
}
