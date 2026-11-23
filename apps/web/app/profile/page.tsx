"use client";

import React, { useState, useEffect, useRef } from "react";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api-client";
import {
  ProfileDTO,
  Lifestyle10DimensionDTO,
  DealbreakerDTO,
  PrivacySettingsDTO,
  UserTrustStatusDTO,
  SendOtpResponse,
  VerifyOtpResponse,
} from "@flatmate/contracts";
import { Card, Button, Input, Badge, Avatar } from "@flatmate/ui";
import {
  User,
  Sparkles,
  ShieldCheck,
  Lock,
  Upload,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Clock,
  Sun,
  Moon,
  Cigarette,
  Dog,
  Utensils,
  Briefcase,
  Home,
  Shield,
  Key,
  Ban,
  Phone,
  Mail,
  UserX,
} from "lucide-react";

interface BlockedUser {
  id: string;
  blocked_user_id: string;
  created_at: string;
}

export default function ProfilePage() {
  const { user, isAuthenticated, refreshUser } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [activeTab, setActiveTab] = useState<
    "profile" | "lifestyle" | "dealbreakers" | "privacy" | "verification" | "account"
  >("profile");

  // Profile Data
  const [profile, setProfile] = useState<ProfileDTO | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [occupation, setOccupation] = useState("");
  const [budgetMin, setBudgetMin] = useState("10000");
  const [budgetMax, setBudgetMax] = useState("25000");
  const [preferredLocations, setPreferredLocations] = useState("");
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);

  // Lifestyle Data
  const [lifestyle, setLifestyle] = useState<Lifestyle10DimensionDTO | null>(null);
  const [sleepSchedule, setSleepSchedule] = useState("early_bird");
  const [cleanliness, setCleanliness] = useState(4);
  const [workArrangement, setWorkArrangement] = useState("hybrid");
  const [diet, setDiet] = useState("pure_veg");
  const [smoking, setSmoking] = useState("never");
  const [pets, setPets] = useState("cats_and_dogs_ok");
  const [socialBattery, setSocialBattery] = useState("balanced");
  const [noiseTolerance, setNoiseTolerance] = useState("moderate");
  const [guestsPolicy, setGuestsPolicy] = useState("occasional_weekends");
  const [isSavingLifestyle, setIsSavingLifestyle] = useState(false);
  const [lifestyleSuccess, setLifestyleSuccess] = useState(false);

  // Dealbreakers
  const [dealbreakers, setDealbreakers] = useState<DealbreakerDTO[]>([]);
  const [dealbreakerRule, setDealbreakerRule] = useState("no_smoking_inside");
  const [dealbreakerValue, setDealbreakerValue] = useState("never");
  const [isStrictDealbreaker, setIsStrictDealbreaker] = useState(true);
  const [isAddingDealbreaker, setIsAddingDealbreaker] = useState(false);

  // Privacy Settings
  const [privacy, setPrivacy] = useState<PrivacySettingsDTO | null>(null);
  const [phonePublic, setPhonePublic] = useState(false);
  const [allowDirectMessages, setAllowDirectMessages] = useState(true);
  const [isSavingPrivacy, setIsSavingPrivacy] = useState(false);
  const [privacySuccess, setPrivacySuccess] = useState(false);

  // Verification & Trust
  const [trustStatus, setTrustStatus] = useState<UserTrustStatusDTO | null>(null);
  const [verifyType, setVerifyType] = useState("government_id");
  const [isSubmittingVerify, setIsSubmittingVerify] = useState(false);
  const [verifySuccess, setVerifySuccess] = useState(false);

  // Account & Safety Settings
  // null = untouched, so the field follows the saved number once the user has loaded.
  const [phoneDraft, setPhoneDraft] = useState<string | null>(null);
  const phoneNumber = phoneDraft ?? user?.phone_number ?? "";
  const [otpSentTo, setOtpSentTo] = useState<string | null>(null);
  const [otpCode, setOtpCode] = useState("");
  const [otpBusy, setOtpBusy] = useState<"send" | "verify" | null>(null);
  const [otpError, setOtpError] = useState<string | null>(null);
  const [otpDevCode, setOtpDevCode] = useState<string | null>(null);
  const [resendAt, setResendAt] = useState<number | null>(null);
  const [clock, setClock] = useState(() => Date.now());
  const [blockedUsers, setBlockedUsers] = useState<BlockedUser[]>([]);
  const [passwordNotice, setPasswordNotice] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // Ticks only while a resend cooldown is running.
  useEffect(() => {
    if (resendAt === null) return;
    const id = setInterval(() => {
      const now = Date.now();
      setClock(now);
      if (now >= resendAt) setResendAt(null);
    }, 1000);
    return () => clearInterval(id);
  }, [resendAt]);
  const resendIn = resendAt === null ? 0 : Math.max(0, Math.ceil((resendAt - clock) / 1000));
  const lastTen = (value: string | null | undefined) => (value || "").replace(/\D/g, "").slice(-10);
  const phoneIsVerified =
    !!user?.phone_verified && !!user.phone_number && lastTen(phoneNumber) === lastTen(user.phone_number);

  useEffect(() => {
    if (!isAuthenticated) return;

    // Load Profile
    apiClient<ProfileDTO>("/profiles/me")
      .then((p) => {
        if (p) {
          setProfile(p);
          setDisplayName(p.display_name || "");
          setBio(p.bio || "");
          setOccupation(p.occupation || p.designation || "");
          setBudgetMin(String(p.budget_min ?? 10000));
          setBudgetMax(String(p.budget_max ?? 25000));
          setPreferredLocations((p.preferred_locations || []).join(", "));
          setAvatarUrl(p.avatar_url || null);
        }
      })
      .catch(() => {});

    // Load Lifestyle
    apiClient<Lifestyle10DimensionDTO>("/lifestyle/me")
      .then((l) => {
        if (l) {
          setLifestyle(l);
          if (l.sleep_schedule) setSleepSchedule(l.sleep_schedule);
          if (l.cleanliness_level) setCleanliness(Number(l.cleanliness_level));
          if (l.work_arrangement) setWorkArrangement(l.work_arrangement);
          if (l.diet_preference) setDiet(l.diet_preference);
          if (l.smoking) setSmoking(l.smoking);
          if (l.pet_preference) setPets(l.pet_preference);
          if (l.social_battery) setSocialBattery(l.social_battery);
          if (l.noise_tolerance) setNoiseTolerance(l.noise_tolerance);
          if (l.guests_policy) setGuestsPolicy(l.guests_policy);
        }
      })
      .catch(() => {});

    // Load Dealbreakers
    apiClient<DealbreakerDTO[]>("/lifestyle/dealbreakers")
      .then((dbs) => setDealbreakers(dbs || []))
      .catch(() => {});

    // Load Privacy
    apiClient<PrivacySettingsDTO>("/profiles/me/privacy")
      .then((priv) => {
        if (priv) {
          setPrivacy(priv);
          setPhonePublic(priv.show_phone_publicly ?? false);
          setAllowDirectMessages(priv.allow_direct_messages ?? true);
        }
      })
      .catch(() => {});

    // Load Trust Status
    apiClient<UserTrustStatusDTO>("/verification/status")
      .then(setTrustStatus)
      .catch(() => {});

    // Load Blocked Users
    apiClient<BlockedUser[]>("/moderation/blocks")
      .then((blocks) => setBlockedUsers(blocks || []))
      .catch(() => {});
  }, [isAuthenticated]);

  // Handle Avatar File Upload
  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploadingAvatar(true);
      const formData = new FormData();
      formData.append("file", file);
      formData.append("bucket", "avatars");

      const uploadRes = await apiClient.upload<{ file_url: string }>("/storage/upload", formData);
      if (uploadRes?.file_url) {
        setAvatarUrl(uploadRes.file_url);
        await apiClient<ProfileDTO>("/profiles/me", {
          method: "PUT",
          body: JSON.stringify({ avatar_url: uploadRes.file_url }),
        });
        setActionNotice("Profile avatar updated successfully!");
        setTimeout(() => setActionNotice(null), 3000);
      }
    } catch (err: any) {
      alert(err.message || "Avatar upload failed");
    } finally {
      setUploadingAvatar(false);
    }
  };

  // Save Profile Details
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
      setProfileSuccess(true);
      setTimeout(() => setProfileSuccess(false), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to update profile");
    } finally {
      setIsSavingProfile(false);
    }
  };

  // Save Lifestyle Questionnaire
  const handleSaveLifestyle = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingLifestyle(true);
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

      setLifestyleSuccess(true);
      setTimeout(() => setLifestyleSuccess(false), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to save questionnaire");
    } finally {
      setIsSavingLifestyle(false);
    }
  };

  // Add Dealbreaker
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
    } catch (err: any) {
      alert(err.message || "Failed to add dealbreaker");
    } finally {
      setIsAddingDealbreaker(false);
    }
  };

  // Delete Dealbreaker
  const handleDeleteDealbreaker = async (id: string) => {
    try {
      await apiClient(`/lifestyle/dealbreakers/${id}`, { method: "DELETE" });
      setDealbreakers((prev) => prev.filter((d) => d.id !== id));
    } catch (err: any) {
      alert(err.message || "Failed to delete dealbreaker");
    }
  };

  // Save Privacy
  const handleSavePrivacy = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingPrivacy(true);
    try {
      const updated = await apiClient<PrivacySettingsDTO>("/profiles/me/privacy", {
        method: "PUT",
        body: JSON.stringify({
          show_phone_publicly: phonePublic,
          allow_direct_messages: allowDirectMessages,
        }),
      });
      setPrivacy(updated);
      setPrivacySuccess(true);
      setTimeout(() => setPrivacySuccess(false), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to save privacy settings");
    } finally {
      setIsSavingPrivacy(false);
    }
  };

  // Submit Verification Document
  const handleSubmitVerification = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmittingVerify(true);
    try {
      await apiClient("/verification/submit", {
        method: "POST",
        body: JSON.stringify({
          verification_type: verifyType,
          document_url: "https://documents.flatmate.platform/v/govt_verified.pdf",
        }),
      });
      setVerifySuccess(true);
      const updatedTrust = await apiClient<UserTrustStatusDTO>("/verification/status").catch(() => null);
      if (updatedTrust) setTrustStatus(updatedTrust);
      setTimeout(() => setVerifySuccess(false), 3000);
    } catch (err: any) {
      alert(err.message || "Verification submission failed");
    } finally {
      setIsSubmittingVerify(false);
    }
  };

  // Phone verification: the number is saved on the account only once the SMS code is confirmed.
  const handleSendPhoneCode = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const phone = phoneNumber.trim();
    if (!phone) return;
    setOtpError(null);
    setOtpBusy("send");
    try {
      const res = await apiClient<SendOtpResponse>("/auth/otp/send", {
        method: "POST",
        body: JSON.stringify({ phone_number: phone }),
      });
      if (res.already_verified) {
        setOtpSentTo(null);
        setActionNotice("This number is already verified.");
        setTimeout(() => setActionNotice(null), 3000);
        return;
      }
      const now = Date.now();
      setOtpSentTo(phone);
      setOtpCode("");
      setOtpDevCode(res.dev_code ?? null);
      setClock(now);
      setResendAt(now + (res.resend_after ?? 60) * 1000);
    } catch (err: any) {
      setOtpError(err.message || "Could not send the code. Please try again.");
    } finally {
      setOtpBusy(null);
    }
  };

  const handleVerifyPhoneCode = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otpSentTo || !/^\d{6}$/.test(otpCode)) {
      setOtpError("Enter the 6-digit code from the SMS.");
      return;
    }
    setOtpError(null);
    setOtpBusy("verify");
    try {
      await apiClient<VerifyOtpResponse>("/auth/otp/verify", {
        method: "POST",
        body: JSON.stringify({ phone_number: otpSentTo, otp_code: otpCode }),
      });
      setOtpSentTo(null);
      setOtpCode("");
      setOtpDevCode(null);
      setResendAt(null);
      setPhoneDraft(null);
      await refreshUser();
      setActionNotice("Mobile number verified.");
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err: any) {
      setOtpError(err.message || "Verification failed. Please try again.");
    } finally {
      setOtpBusy(null);
    }
  };

  // Request Password Reset
  const handleRequestPasswordReset = async () => {
    if (!user?.email) return;
    try {
      await apiClient("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email: user.email }),
      });
      setPasswordNotice("Password reset link has been dispatched to your registered email address.");
      setTimeout(() => setPasswordNotice(null), 5000);
    } catch (err: any) {
      alert(err.message || "Failed to request password reset");
    }
  };

  // Unblock User
  const handleUnblockUser = async (blockedUserId: string) => {
    try {
      await apiClient(`/moderation/blocks/${blockedUserId}`, { method: "DELETE" });
      setBlockedUsers((prev) => prev.filter((b) => b.blocked_user_id !== blockedUserId && b.id !== blockedUserId));
      setActionNotice("User unblocked successfully.");
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to unblock user");
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto py-20 px-4 text-center">
        <Card className="p-8">
          <Lock className="w-10 h-10 text-forest mx-auto mb-3" />
          <h2 className="text-xl font-bold text-charcoal mb-2">Sign In Required</h2>
          <p className="text-xs text-charcoal-muted mb-6">You must be logged in to access and edit your profile.</p>
          <Button variant="primary" onClick={() => (window.location.href = "/login")} className="w-full">
            Log In Now
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Profile Header Summary */}
      <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-xs flex flex-col md:flex-row items-center gap-6">
        <div className="relative">
          <Avatar
            src={avatarUrl || undefined}
            alt={displayName || user?.full_name || "User"}
            size="xl"
            isVerified={trustStatus?.is_fully_verified ?? user?.is_verified}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadingAvatar}
            className="absolute bottom-0 right-0 p-2 bg-forest text-white rounded-full shadow-md hover:bg-forest-secondary transition-colors"
            title="Upload Profile Picture"
          >
            <Upload className="w-3.5 h-3.5" />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            onChange={handleAvatarUpload}
          />
        </div>

        <div className="flex-1 text-center md:text-left">
          <div className="flex flex-wrap items-center justify-center md:justify-start gap-2 mb-1">
            <h1 className="text-2xl font-bold text-charcoal">{displayName || user?.full_name}</h1>
            {trustStatus?.is_fully_verified && (
              <Badge variant="forest">
                <ShieldCheck className="w-3 h-3 mr-1 inline" /> Verified Resident
              </Badge>
            )}
            <Badge variant="default" className="uppercase text-[10px] tracking-wider">
              {user?.role || "Seeker"}
            </Badge>
          </div>
          <p className="text-xs text-charcoal-muted mb-2">{user?.email}</p>
          <p className="text-sm text-charcoal max-w-xl">
            {bio || "Tell roommates about yourself, your hobbies, and what you look for in a flatmate."}
          </p>
        </div>

        <div className="text-right flex flex-col items-center md:items-end">
          <div className="text-xs text-charcoal-muted">Trust Score</div>
          <div className="text-2xl font-black text-forest">
            {trustStatus?.total_trust_score ?? 60}
            <span className="text-xs font-normal text-charcoal-muted">/100</span>
          </div>
          <div className="text-[11px] text-emerald-600 flex items-center gap-1 mt-1 font-medium">
            <CheckCircle2 className="w-3 h-3" /> Account Active
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
      <div className="flex border-b border-slate-200 mb-6 space-x-2 overflow-x-auto">
        <button
          onClick={() => setActiveTab("profile")}
          className={`pb-3 px-4 text-xs font-semibold border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
            activeTab === "profile" ? "border-forest text-forest font-bold" : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          <User className="w-4 h-4" /> Basic Profile
        </button>
        <button
          onClick={() => setActiveTab("lifestyle")}
          className={`pb-3 px-4 text-xs font-semibold border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
            activeTab === "lifestyle" ? "border-forest text-forest font-bold" : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          <Sparkles className="w-4 h-4" /> 10-D Questionnaire
        </button>
        <button
          onClick={() => setActiveTab("dealbreakers")}
          className={`pb-3 px-4 text-xs font-semibold border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
            activeTab === "dealbreakers" ? "border-forest text-forest font-bold" : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          <Shield className="w-4 h-4" /> Dealbreakers
        </button>
        <button
          onClick={() => setActiveTab("privacy")}
          className={`pb-3 px-4 text-xs font-semibold border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
            activeTab === "privacy" ? "border-forest text-forest font-bold" : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          <Lock className="w-4 h-4" /> Privacy Controls
        </button>
        <button
          onClick={() => setActiveTab("verification")}
          className={`pb-3 px-4 text-xs font-semibold border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
            activeTab === "verification" ? "border-forest text-forest font-bold" : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          <ShieldCheck className="w-4 h-4" /> Trust & Verification
        </button>
        <button
          onClick={() => setActiveTab("account")}
          className={`pb-3 px-4 text-xs font-semibold border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
            activeTab === "account" ? "border-forest text-forest font-bold" : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          <Key className="w-4 h-4" /> Account & Security
        </button>
      </div>

      {/* Tab 1: Basic Profile */}
      {activeTab === "profile" && (
        <Card className="p-6 max-w-2xl">
          <div className="mb-6">
            <h2 className="text-lg font-bold text-charcoal">Public Profile Settings</h2>
            <p className="text-xs text-charcoal-muted mt-1">
              Your profile is visible to other room seekers and landlords looking for flatmates.
            </p>
          </div>

          {profileSuccess && (
            <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs rounded-xl flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" /> Profile details saved!
            </div>
          )}

          <form onSubmit={handleSaveProfile} className="space-y-4">
            <Input
              label="Full Display Name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="e.g. Rahul Sharma"
              required
            />

            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1">About Me (Bio)</label>
              <textarea
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                rows={3}
                className="w-full text-xs rounded-xl border border-slate-200 p-2.5 focus:ring-2 focus:ring-forest focus:outline-none"
                placeholder="Software engineer at a startup. Usually quiet on weekdays, likes hiking on weekends..."
              />
            </div>

            <Input
              label="Occupation / Designation"
              value={occupation}
              onChange={(e) => setOccupation(e.target.value)}
              placeholder="e.g. Product Designer"
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
              label="Preferred Localities / Areas (comma separated)"
              value={preferredLocations}
              onChange={(e) => setPreferredLocations(e.target.value)}
              placeholder="e.g. Koramangala, Indiranagar, HSR Layout"
            />

            <Button type="submit" variant="primary" isLoading={isSavingProfile}>
              Save Profile
            </Button>
          </form>
        </Card>
      )}

      {/* Tab 2: Lifestyle */}
      {activeTab === "lifestyle" && (
        <Card className="p-6 max-w-2xl">
          <div className="mb-6">
            <h2 className="text-lg font-bold text-charcoal">10-Dimension Lifestyle Preferences</h2>
            <p className="text-xs text-charcoal-muted mt-1">
              Used by the vector AI compatibility engine to calculate pairwise compatibility scores.
            </p>
          </div>

          {lifestyleSuccess && (
            <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs rounded-xl flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" /> Lifestyle matrix updated!
            </div>
          )}

          <form onSubmit={handleSaveLifestyle} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-charcoal mb-1 flex items-center gap-1.5">
                  <Sun className="w-3.5 h-3.5 text-amber-500" /> Sleep Schedule
                </label>
                <select
                  value={sleepSchedule}
                  onChange={(e) => setSleepSchedule(e.target.value)}
                  className="w-full text-xs rounded-xl border border-slate-200 p-2.5 focus:ring-2 focus:ring-forest"
                >
                  <option value="early_bird">Early Bird (Sleeps by 11pm)</option>
                  <option value="night_owl">Night Owl (Sleeps after 1am)</option>
                  <option value="flexible">Flexible / Variable Hours</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-charcoal mb-1">Cleanliness Standard</label>
                <input
                  type="range"
                  min="1"
                  max="5"
                  value={cleanliness}
                  onChange={(e) => setCleanliness(parseInt(e.target.value, 10))}
                  className="w-full accent-forest"
                />
                <div className="flex justify-between text-[11px] text-charcoal-muted mt-1">
                  <span>Relaxed (1)</span>
                  <span className="font-bold text-forest">Level {cleanliness}</span>
                  <span>Spotless (5)</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-charcoal mb-1 flex items-center gap-1.5">
                  <Briefcase className="w-3.5 h-3.5 text-charcoal-muted" /> Work Arrangement
                </label>
                <select
                  value={workArrangement}
                  onChange={(e) => setWorkArrangement(e.target.value)}
                  className="w-full text-xs rounded-xl border border-slate-200 p-2.5 focus:ring-2 focus:ring-forest"
                >
                  <option value="remote">Work from Home (100% Remote)</option>
                  <option value="hybrid">Hybrid (2-3 days office)</option>
                  <option value="office">Work from Office (Full-time)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-charcoal mb-1 flex items-center gap-1.5">
                  <Utensils className="w-3.5 h-3.5 text-forest" /> Food & Dietary Habit
                </label>
                <select
                  value={diet}
                  onChange={(e) => setDiet(e.target.value)}
                  className="w-full text-xs rounded-xl border border-slate-200 p-2.5 focus:ring-2 focus:ring-forest"
                >
                  <option value="pure_veg">Pure Vegetarian</option>
                  <option value="eggetarian">Eggetarian</option>
                  <option value="non_veg">Non-Vegetarian</option>
                  <option value="vegan">Vegan</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-charcoal mb-1 flex items-center gap-1.5">
                  <Cigarette className="w-3.5 h-3.5 text-rose-500" /> Smoking Habits
                </label>
                <select
                  value={smoking}
                  onChange={(e) => setSmoking(e.target.value)}
                  className="w-full text-xs rounded-xl border border-slate-200 p-2.5 focus:ring-2 focus:ring-forest"
                >
                  <option value="never">Non-Smoker (Never)</option>
                  <option value="outside_only">Smokes Outside Only</option>
                  <option value="permitted">Smoking Permitted</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-charcoal mb-1 flex items-center gap-1.5">
                  <Dog className="w-3.5 h-3.5 text-amber-600" /> Pet Preference
                </label>
                <select
                  value={pets}
                  onChange={(e) => setPets(e.target.value)}
                  className="w-full text-xs rounded-xl border border-slate-200 p-2.5 focus:ring-2 focus:ring-forest"
                >
                  <option value="cats_and_dogs_ok">Love Cats & Dogs</option>
                  <option value="cats_only">Cats Only</option>
                  <option value="dogs_only">Dogs Only</option>
                  <option value="no_pets">Strictly No Pets</option>
                </select>
              </div>
            </div>

            <Button type="submit" variant="primary" isLoading={isSavingLifestyle}>
              Save Lifestyle Profile
            </Button>
          </form>
        </Card>
      )}

      {/* Tab 3: Dealbreakers */}
      {activeTab === "dealbreakers" && (
        <Card className="p-6">
          <div className="mb-6">
            <h2 className="text-lg font-bold text-charcoal">Non-Negotiable Dealbreakers</h2>
            <p className="text-xs text-charcoal-muted mt-1">
              Set hard constraints. Any prospective flatmate who violates these will be automatically flagged or excluded from matching.
            </p>
          </div>

          <form onSubmit={handleAddDealbreaker} className="bg-warm p-4 rounded-xl border border-slate-200/80 mb-6 flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-semibold text-charcoal mb-1">Dealbreaker Rule</label>
              <select
                value={dealbreakerRule}
                onChange={(e) => setDealbreakerRule(e.target.value)}
                className="w-full text-xs rounded-xl border border-slate-200 p-2 bg-white"
              >
                <option value="no_smoking_inside">No Smoking Inside Flat</option>
                <option value="strictly_vegetarian_kitchen">Strictly Vegetarian Kitchen</option>
                <option value="no_pets_allowed">No Pets Allowed</option>
                <option value="no_late_night_parties">No Late Night Parties</option>
              </select>
            </div>

            <div className="flex items-center gap-2 h-9 px-3 bg-white border border-slate-200 rounded-xl">
              <input
                id="strict"
                type="checkbox"
                checked={isStrictDealbreaker}
                onChange={(e) => setIsStrictDealbreaker(e.target.checked)}
                className="h-4 w-4 rounded accent-forest"
              />
              <label htmlFor="strict" className="text-xs font-semibold text-charcoal">Strict Elimination</label>
            </div>

            <Button type="submit" variant="primary" size="sm" isLoading={isAddingDealbreaker}>
              <Plus className="w-3.5 h-3.5 mr-1" /> Add Rule
            </Button>
          </form>

          <div className="space-y-2">
            {dealbreakers.length === 0 ? (
              <p className="text-xs text-charcoal-muted py-4 text-center">No dealbreakers configured yet.</p>
            ) : (
              dealbreakers.map((db) => (
                <div key={db.id} className="flex items-center justify-between p-3 bg-white rounded-xl border border-slate-200">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-rose-500" />
                    <span className="text-xs font-bold text-charcoal">{db.rule_key.replace(/_/g, " ").toUpperCase()}</span>
                    {db.is_strict && <Badge variant="danger" className="text-[10px]">Strict</Badge>}
                  </div>
                  <button
                    onClick={() => handleDeleteDealbreaker(db.id)}
                    className="text-slate-400 hover:text-rose-600 transition-colors p-1"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))
            )}
          </div>
        </Card>
      )}

      {/* Tab 4: Privacy Controls */}
      {activeTab === "privacy" && (
        <Card className="p-6 max-w-2xl">
          <div className="mb-6">
            <h2 className="text-lg font-bold text-charcoal">Privacy & Visibility Controls</h2>
            <p className="text-xs text-charcoal-muted mt-1">
              Control what contact information other flatmates can see before a confirmed match or appointment.
            </p>
          </div>
          {privacySuccess && (
            <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs rounded-xl flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" /> Privacy settings updated!
            </div>
          )}
          <form onSubmit={handleSavePrivacy} className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-warm rounded-xl border border-slate-200/80">
              <div>
                <div className="text-xs font-bold text-charcoal">Show Mobile Number Publicly</div>
                <div className="text-[11px] text-charcoal-muted">Allow other verified users to see your contact phone number.</div>
              </div>
              <input
                type="checkbox"
                checked={phonePublic}
                onChange={(e) => setPhonePublic(e.target.checked)}
                className="h-5 w-5 rounded accent-forest"
              />
            </div>

            <div className="flex items-center justify-between p-4 bg-warm rounded-xl border border-slate-200/80">
              <div>
                <div className="text-xs font-bold text-charcoal">Allow Direct Messages</div>
                <div className="text-[11px] text-charcoal-muted">Permit room seekers and hosts to initiate chat conversations.</div>
              </div>
              <input
                type="checkbox"
                checked={allowDirectMessages}
                onChange={(e) => setAllowDirectMessages(e.target.checked)}
                className="h-5 w-5 rounded accent-forest"
              />
            </div>

            <Button type="submit" variant="primary" isLoading={isSavingPrivacy}>
              Save Privacy Settings
            </Button>
          </form>
        </Card>
      )}

      {/* Tab 5: Verification & Trust */}
      {activeTab === "verification" && (
        <Card className="p-6 max-w-2xl">
          <div className="mb-6">
            <h2 className="text-lg font-bold text-charcoal">Resident Trust & Safety Verification</h2>
            <p className="text-xs text-charcoal-muted mt-1">
              Verified badges boost response rates by up to 3x. Your documents are securely processed and never shared publicly.
            </p>
          </div>
          {verifySuccess && (
            <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs rounded-xl flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" /> Verification document submitted for manual review!
            </div>
          )}

          <div className="bg-forest-pale/60 border border-forest/20 rounded-xl p-4 mb-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <ShieldCheck className="w-8 h-8 text-forest" />
              <div>
                <div className="text-xs font-bold text-forest">Verification Status</div>
                <div className="text-xs text-forest/80 capitalize">
                  {trustStatus?.is_fully_verified ? "Fully Verified Account" : "Pending Verification Submission"}
                </div>
              </div>
            </div>
            <div className="text-right">
              <span className="text-xs text-charcoal-muted">Trust Score</span>
              <div className="text-xl font-bold text-forest">{trustStatus?.total_trust_score ?? 60}/100</div>
            </div>
          </div>

          <form onSubmit={handleSubmitVerification} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1">Verification Document Type</label>
              <select
                value={verifyType}
                onChange={(e) => setVerifyType(e.target.value)}
                className="w-full text-xs rounded-xl border border-slate-200 p-2.5 bg-white"
              >
                <option value="government_id">Government ID (Aadhaar / Passport / Voter ID)</option>
                <option value="employment">Corporate Work Email / Offer Letter</option>
                <option value="student_id">University / College Student ID</option>
              </select>
            </div>

            <Button type="submit" variant="primary" isLoading={isSubmittingVerify}>
              Submit Verification Request
            </Button>
          </form>
        </Card>
      )}

      {/* Tab 6: Account & Security */}
      {activeTab === "account" && (
        <div className="space-y-6 max-w-2xl">
          {passwordNotice && (
            <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-2xl text-xs font-semibold flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{passwordNotice}</span>
            </div>
          )}

          {/* Account Details & Email Verification */}
          <Card className="p-6">
            <h2 className="text-lg font-bold text-charcoal mb-1">Account & Identity</h2>
            <p className="text-xs text-charcoal-muted mb-4">Core authentication credentials and contact verification.</p>

            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between p-3 bg-warm rounded-xl border border-slate-200/60">
                <div className="flex items-center gap-2">
                  <Mail className="w-4 h-4 text-forest" />
                  <div>
                    <span className="font-semibold text-charcoal block">{user?.email}</span>
                    <span className="text-[10px] text-charcoal-muted">Primary account login</span>
                  </div>
                </div>
                <Badge variant={user?.is_verified ? "forest" : "warning"}>
                  {user?.is_verified ? "Email Verified" : "Verification Pending"}
                </Badge>
              </div>

              {/* Phone Number Edit */}
              <div className="p-3 bg-warm rounded-xl border border-slate-200/60 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <label htmlFor="phone-number" className="font-semibold text-charcoal block">
                    Mobile Phone Number
                  </label>
                  {phoneIsVerified ? (
                    <Badge variant="forest">Verified</Badge>
                  ) : user?.phone_number && phoneDraft === null ? (
                    <Badge variant="warning">Not verified</Badge>
                  ) : null}
                </div>
                <form onSubmit={handleSendPhoneCode} className="flex flex-col sm:flex-row gap-2">
                  <Input
                    id="phone-number"
                    type="tel"
                    inputMode="tel"
                    autoComplete="tel"
                    value={phoneNumber}
                    onChange={(e) => {
                      setPhoneDraft(e.target.value);
                      setOtpSentTo(null);
                      setOtpError(null);
                    }}
                    placeholder="+91 98765 43210"
                    className="flex-1 text-xs"
                  />
                  {!phoneIsVerified && (
                    <Button
                      type="submit"
                      size="sm"
                      variant="primary"
                      isLoading={otpBusy === "send"}
                      disabled={!phoneNumber.trim() || otpBusy !== null || (!!otpSentTo && resendIn > 0)}
                    >
                      {otpSentTo ? (resendIn > 0 ? `Resend in ${resendIn}s` : "Resend code") : "Send code"}
                    </Button>
                  )}
                </form>

                {otpSentTo && (
                  <form onSubmit={handleVerifyPhoneCode} className="space-y-2">
                    <label htmlFor="phone-otp" className="text-[11px] text-charcoal-muted block">
                      Enter the 6-digit code sent to {otpSentTo}
                    </label>
                    <div className="flex flex-col sm:flex-row gap-2">
                      <Input
                        id="phone-otp"
                        value={otpCode}
                        onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                        inputMode="numeric"
                        autoComplete="one-time-code"
                        maxLength={6}
                        placeholder="123456"
                        className="flex-1 text-xs tracking-[0.3em]"
                      />
                      <Button
                        type="submit"
                        size="sm"
                        variant="primary"
                        isLoading={otpBusy === "verify"}
                        disabled={otpCode.length !== 6 || otpBusy !== null}
                      >
                        Verify
                      </Button>
                    </div>
                    {otpDevCode && (
                      <span className="text-[10px] text-amber-700 block">
                        Development server: your code is {otpDevCode}
                      </span>
                    )}
                  </form>
                )}

                {otpError && (
                  <p role="alert" className="text-[11px] text-red-600 flex items-center gap-1">
                    <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                    {otpError}
                  </p>
                )}
                <span className="text-[10px] text-charcoal-muted block">
                  We text a one-time code to confirm the number. Used for urgent tenancy notifications.
                </span>
              </div>

              {/* Password Management */}
              <div className="p-4 bg-warm rounded-xl border border-slate-200/60 flex items-center justify-between">
                <div>
                  <span className="font-semibold text-charcoal block">Security & Password</span>
                  <span className="text-[10px] text-charcoal-muted">Request a secure password reset link to your email.</span>
                </div>
                <Button size="sm" variant="outline" onClick={handleRequestPasswordReset}>
                  Reset Password
                </Button>
              </div>
            </div>
          </Card>

          {/* Blocked Users */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-base font-bold text-charcoal">Blocked Users ({blockedUsers.length})</h3>
              <Ban className="w-4 h-4 text-rose-500" />
            </div>
            <p className="text-xs text-charcoal-muted mb-4">
              Blocked users cannot initiate messages, view your full profile, or send matching requests.
            </p>

            {blockedUsers.length === 0 ? (
              <p className="text-xs text-charcoal-muted italic py-2">No users currently blocked.</p>
            ) : (
              <div className="space-y-2">
                {blockedUsers.map((b) => (
                  <div key={b.id || b.blocked_user_id} className="p-3 bg-warm rounded-xl border border-slate-200 flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <UserX className="w-4 h-4 text-rose-500" />
                      <span className="text-charcoal font-medium">User #{b.blocked_user_id.slice(0, 8)}</span>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-xs"
                      onClick={() => handleUnblockUser(b.blocked_user_id || b.id)}
                    >
                      Unblock
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* DPDP Act 2023 Compliance & Data Deletion */}
          <Card className="p-6 border-forest/20 bg-forest-pale/20">
            <div className="flex items-center gap-2 mb-2">
              <Shield className="w-5 h-5 text-forest" />
              <h3 className="text-sm font-bold text-charcoal">Data Rights & DPDP Act 2023 Compliance</h3>
            </div>
            <p className="text-xs text-charcoal-muted leading-relaxed">
              Under India&apos;s Digital Personal Data Protection Act (DPDP Act 2023), you hold the right to summary of personal data, right to correction, and right to erasure of your personal data.
            </p>
            <div className="mt-3 pt-3 border-t border-forest/10 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
              <span className="text-charcoal-muted">To request complete account deactivation or data deletion:</span>
              <a
                href="mailto:privacy@flatmate.platform?subject=DPDP%20Data%20Erasure%20Request"
                className="font-bold text-forest hover:underline"
              >
                Contact Data Protection Officer →
              </a>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
