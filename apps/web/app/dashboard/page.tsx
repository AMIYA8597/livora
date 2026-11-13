"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api-client";
import { ApplicationDTO, ProfileDTO, LifestyleQuizInput } from "@flatmate/contracts";
import { Card, Button, Input, Badge, Avatar } from "@flatmate/ui";
import { formatCurrency, formatDate } from "@/lib/utils";
import {
  LayoutDashboard, FileText, CheckCircle2, Clock, XCircle, ShieldCheck, Sparkles, Sun, Moon
} from "lucide-react";

export default function DashboardPage() {
  const { user, isAuthenticated } = useAuth();
  const [applications, setApplications] = useState<ApplicationDTO[]>([]);
  const [profile, setProfile] = useState<ProfileDTO | null>(null);
  const [activeTab, setActiveTab] = useState<"applications" | "quiz">("applications");

  // Lifestyle Quiz Form State
  const [sleepSchedule, setSleepSchedule] = useState("early_bird");
  const [cleanliness, setCleanliness] = useState(5);
  const [diet, setDiet] = useState("vegan");
  const [smoking, setSmoking] = useState("never");
  const [pets, setPets] = useState("cats_ok");
  const [socialBattery, setSocialBattery] = useState("moderate");
  const [workArrangement, setWorkArrangement] = useState("hybrid");
  const [isSavingQuiz, setIsSavingQuiz] = useState(false);
  const [quizSavedSuccess, setQuizSavedSuccess] = useState(false);

  useEffect(() => {
    async function loadDashboardData() {
      if (!isAuthenticated) return;
      try {
        const [appsData, profileData] = await Promise.all([
          apiClient<ApplicationDTO[]>("/applications/me"),
          apiClient<ProfileDTO>("/profiles/me"),
        ]);
        setApplications(appsData);
        setProfile(profileData);

        if (profileData.lifestyle_traits) {
          const t = profileData.lifestyle_traits;
          if (t.sleep_schedule) setSleepSchedule(t.sleep_schedule);
          if (t.cleanliness_level) setCleanliness(t.cleanliness_level);
          if (t.diet) setDiet(t.diet);
          if (t.smoking) setSmoking(t.smoking);
          if (t.pets) setPets(t.pets);
          if (t.social_battery) setSocialBattery(t.social_battery);
          if (t.work_arrangement) setWorkArrangement(t.work_arrangement);
        }
      } catch (err) {
        console.error("Dashboard data load error:", err);
      }
    }
    loadDashboardData();
  }, [isAuthenticated]);

  const handleSaveQuiz = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingQuiz(true);
    try {
      const payload: LifestyleQuizInput = {
        sleep_schedule: sleepSchedule as any,
        cleanliness_level: cleanliness as any,
        social_battery: socialBattery as any,
        work_arrangement: workArrangement as any,
        diet: diet as any,
        smoking: smoking as any,
        pets: pets as any,
        guests_policy: "occasional_weekends",
      };
      await apiClient("/profiles/me/quiz", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setQuizSavedSuccess(true);
      setTimeout(() => setQuizSavedSuccess(false), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to update lifestyle quiz");
    } finally {
      setIsSavingQuiz(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <LayoutDashboard className="w-12 h-12 text-indigo-600 mx-auto mb-3" />
        <h2 className="text-xl font-bold text-slate-900">Please sign in to access your dashboard</h2>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header Profile Bar */}
      <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center space-x-4">
          <Avatar alt={user?.full_name || "User"} size="lg" isVerified={user?.is_verified} />
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-2xl font-bold text-slate-900">{user?.full_name}</h1>
              <span className="text-xs uppercase font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-md">
                {user?.role}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">{user?.email}</p>
          </div>
        </div>

        <div className="flex items-center space-x-3 bg-emerald-50 border border-emerald-200 px-4 py-2.5 rounded-2xl text-emerald-800 text-xs">
          <ShieldCheck className="w-5 h-5 text-emerald-600 shrink-0" />
          <div>
            <span className="font-bold block">Trust & Verification Score: 95/100</span>
            <span className="text-emerald-700/80">Govt ID & Email Verified</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex space-x-2 border-b border-slate-200">
        <button
          onClick={() => setActiveTab("applications")}
          className={`pb-3 px-4 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "applications"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          My Rental Applications ({applications.length})
        </button>
        <button
          onClick={() => setActiveTab("quiz")}
          className={`pb-3 px-4 text-sm font-semibold border-b-2 transition-colors flex items-center space-x-1.5 ${
            activeTab === "quiz"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Sparkles className="w-4 h-4" />
          <span>Lifestyle Compatibility Quiz</span>
        </button>
      </div>

      {/* Tab Content: Applications */}
      {activeTab === "applications" && (
        <div className="space-y-4">
          {applications.length === 0 ? (
            <Card className="p-12 text-center max-w-lg mx-auto">
              <FileText className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <h3 className="text-base font-semibold text-slate-800">No applications sent yet</h3>
              <p className="text-xs text-slate-500 mt-1">
                Browse properties or rooms to submit your introduction to landlords.
              </p>
            </Card>
          ) : (
            applications.map((app) => (
              <Card key={app.id} className="p-5 border-slate-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs text-slate-400 font-mono">App #{app.id.slice(0, 8)}</span>
                    <Badge
                      variant={
                        app.status === "accepted"
                          ? "success"
                          : app.status === "rejected"
                          ? "danger"
                          : "warning"
                      }
                      size="sm"
                      className="capitalize"
                    >
                      {app.status}
                    </Badge>
                  </div>
                  <h4 className="font-semibold text-slate-900 text-base mt-1">
                    Offered Rent: {formatCurrency(app.proposed_rent)}/mo
                  </h4>
                  <p className="text-xs text-slate-500 mt-1">
                    Target Move-In: {formatDate(app.move_in_target)} • Submitted: {formatDate(app.submitted_at)}
                  </p>
                  <p className="text-xs text-slate-600 mt-2 italic bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                    &ldquo;{app.introduction}&rdquo;
                  </p>
                </div>
              </Card>
            ))
          )}
        </div>
      )}

      {/* Tab Content: Lifestyle Quiz Form */}
      {activeTab === "quiz" && (
        <Card className="p-8 border-slate-200/80 max-w-3xl">
          <div className="mb-6">
            <h2 className="text-xl font-bold text-slate-900">Lifestyle Questionnaire</h2>
            <p className="text-xs text-slate-500 mt-1">
              Changes here immediately recalculate your 64-dimensional vector embedding stored via pgvector.
            </p>
          </div>

          {quizSavedSuccess && (
            <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-xs font-semibold flex items-center space-x-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              <span>Lifestyle matrix and vector embeddings updated successfully!</span>
            </div>
          )}

          <form onSubmit={handleSaveQuiz} className="space-y-6">
            {/* Sleep Schedule */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                1. Daily Sleep Schedule
              </label>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { id: "early_bird", label: "Early Bird (6am - 10pm)" },
                  { id: "night_owl", label: "Night Owl (11pm - 8am)" },
                  { id: "flexible", label: "Flexible" },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setSleepSchedule(item.id)}
                    className={`py-3 px-3 rounded-xl border text-xs font-semibold text-center transition-all ${
                      sleepSchedule === item.id
                        ? "bg-indigo-50 border-indigo-600 text-indigo-700 shadow-2xs"
                        : "border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Cleanliness */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  2. Cleanliness Standard
                </label>
                <span className="text-xs font-bold text-indigo-600">{cleanliness} / 5</span>
              </div>
              <input
                type="range"
                min="1"
                max="5"
                step="1"
                value={cleanliness}
                onChange={(e) => setCleanliness(parseInt(e.target.value, 10))}
                className="w-full accent-indigo-600"
              />
              <div className="flex justify-between text-[11px] text-slate-400 mt-1">
                <span>1 - Relaxed</span>
                <span>3 - Normal tidy</span>
                <span>5 - Spotless after every meal</span>
              </div>
            </div>

            {/* Diet */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                3. Kitchen & Dietary Preference
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {["omnivore", "vegetarian", "vegan", "pescatarian"].map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setDiet(d)}
                    className={`py-2 px-3 rounded-xl border text-xs font-semibold capitalize text-center transition-all ${
                      diet === d
                        ? "bg-indigo-50 border-indigo-600 text-indigo-700 shadow-2xs"
                        : "border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>

            {/* Smoking */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                4. Smoking Policy
              </label>
              <div className="grid grid-cols-3 gap-2">
                {["never", "outside_only", "allowed"].map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setSmoking(s)}
                    className={`py-2 px-3 rounded-xl border text-xs font-semibold capitalize text-center transition-all ${
                      smoking === s
                        ? "bg-indigo-50 border-indigo-600 text-indigo-700 shadow-2xs"
                        : "border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {s.replace(/_/g, " ")}
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
    </div>
  );
}
