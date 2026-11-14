"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api-client";
import { Card, Button, Input, Badge } from "@flatmate/ui";
import {
  Sparkles,
  User,
  ShieldCheck,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Moon,
  Sun,
  Utensils,
  Briefcase,
  Home,
  Check,
} from "lucide-react";

export default function OnboardingPage() {
  const router = useRouter();
  const { isAuthenticated, user } = useAuth();

  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1: Basic Profile
  const [displayName, setDisplayName] = useState(user?.full_name || "");
  const [bio, setBio] = useState("");
  const [occupation, setOccupation] = useState("");
  const [budgetMin, setBudgetMin] = useState("10000");
  const [budgetMax, setBudgetMax] = useState("25000");
  const [preferredLocations, setPreferredLocations] = useState("Koramangala, HSR Layout, Indiranagar");

  // Step 2: 10-Dimension Lifestyle
  const [sleepSchedule, setSleepSchedule] = useState("early_bird");
  const [wakeTime, setWakeTime] = useState("06:30");
  const [sleepTime, setSleepTime] = useState("23:00");
  const [cleanliness, setCleanliness] = useState(4);
  const [workArrangement, setWorkArrangement] = useState("hybrid");
  const [diet, setDiet] = useState("omnivore");
  const [smoking, setSmoking] = useState("never");
  const [drinking, setDrinking] = useState("socially");
  const [socialBattery, setSocialBattery] = useState("balanced");
  const [guestsPolicy, setGuestsPolicy] = useState("occasional_weekends");
  const [pets, setPets] = useState("cats_and_dogs_ok");

  // Step 3: Dealbreakers
  const [strictNonVeg, setStrictNonVeg] = useState(false);
  const [strictSmoking, setStrictSmoking] = useState(true);
  const [strictLateNights, setStrictLateNights] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, router]);

  const handleCompleteOnboarding = async () => {
    setIsSubmitting(true);
    setError(null);

    try {
      // 1. Update Profile
      const locArray = preferredLocations
        .split(",")
        .map((l) => l.trim())
        .filter(Boolean);

      await apiClient("/profiles/me", {
        method: "PUT",
        body: JSON.stringify({
          display_name: displayName,
          bio,
          occupation,
          budget_min: parseFloat(budgetMin) || 10000,
          budget_max: parseFloat(budgetMax) || 25000,
          preferred_locations: locArray,
        }),
      });

      // 2. Submit 10-Dimension Lifestyle
      await apiClient("/lifestyle/me", {
        method: "PUT",
        body: JSON.stringify({
          sleep_schedule: sleepSchedule,
          wake_time_typical: wakeTime,
          sleep_time_typical: sleepTime,
          work_arrangement: workArrangement,
          cleanliness_level: cleanliness,
          chore_philosophy: "shared_roster",
          noise_tolerance: "moderate",
          instrument_or_music: false,
          lighting_preference: "pitch_black",
          guests_policy: guestsPolicy,
          social_battery: socialBattery,
          diet_preference: diet,
          non_veg_cooking_allowed: diet !== "pure_veg",
          cooks_at_home: "daily",
          smoking,
          drinking,
          pet_preference: pets,
        }),
      });

      // 3. Register Selected Strict Dealbreakers
      if (strictSmoking) {
        await apiClient("/lifestyle/dealbreakers", {
          method: "POST",
          body: JSON.stringify({
            rule_key: "no_smoking_inside",
            is_strict: true,
            expected_value: "never",
          }),
        }).catch(() => {});
      }

      if (strictNonVeg) {
        await apiClient("/lifestyle/dealbreakers", {
          method: "POST",
          body: JSON.stringify({
            rule_key: "pure_veg_kitchen_only",
            is_strict: true,
            expected_value: "pure_veg",
          }),
        }).catch(() => {});
      }

      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Failed to save profile. Please check fields and try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-12 space-y-8">
      {/* Step Indicator */}
      <div className="text-center space-y-2">
        <div className="inline-flex items-center space-x-1.5 bg-indigo-50 text-indigo-700 text-xs font-semibold px-3 py-1 rounded-full">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Step {step} of 3 • Welcome Onboard</span>
        </div>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
          {step === 1 && "Personal Profile & Budget"}
          {step === 2 && "10-Dimension Lifestyle Routine"}
          {step === 3 && "Hard Dealbreakers & House Rules"}
        </h1>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          {step === 1 && "Tell future flatmates and landlords about yourself and your target budget."}
          {step === 2 && "Our matching algorithm uses your habits to calculate explainable compatibility."}
          {step === 3 && "Specify absolute zero-tolerance rules so incompatible matches are filtered out."}
        </p>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl text-rose-700 text-xs">
          {error}
        </div>
      )}

      <Card className="p-6 border-slate-200/80 shadow-xs space-y-5">
        {step === 1 && (
          <div className="space-y-4">
            <Input
              label="Display Name / Preferred Name"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="e.g. Rahul Sharma"
            />
            <Input
              label="Occupation / Designation"
              value={occupation}
              onChange={(e) => setOccupation(e.target.value)}
              placeholder="e.g. Frontend Engineer, Product Designer, Student"
            />
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">About You (Bio)</label>
              <textarea
                rows={3}
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                placeholder="Share your hobbies, lifestyle vibe, and what kind of flatmates you get along with best..."
                className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
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
              label="Preferred Localities / Hubs"
              value={preferredLocations}
              onChange={(e) => setPreferredLocations(e.target.value)}
              placeholder="e.g. Koramangala, Indiranagar, HSR Layout"
            />
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Sleep Rhythm</label>
                <select
                  value={sleepSchedule}
                  onChange={(e) => setSleepSchedule(e.target.value)}
                  className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
                >
                  <option value="early_bird">Early Bird (Wake before 7 AM)</option>
                  <option value="night_owl">Night Owl (Late Nights)</option>
                  <option value="flexible">Flexible / Normal</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Work Arrangement</label>
                <select
                  value={workArrangement}
                  onChange={(e) => setWorkArrangement(e.target.value)}
                  className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
                >
                  <option value="remote">Work from Home (Full Remote)</option>
                  <option value="hybrid">Hybrid (2-3 days office)</option>
                  <option value="on_site">Work from Office (All weekdays)</option>
                </select>
              </div>
            </div>

            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs font-semibold text-slate-700">Cleanliness & Tidiness Standard</label>
                <span className="text-xs font-bold text-indigo-600">{cleanliness} / 5</span>
              </div>
              <input
                type="range"
                min="1"
                max="5"
                value={cleanliness}
                onChange={(e) => setCleanliness(parseInt(e.target.value, 10))}
                className="w-full accent-indigo-600"
              />
              <div className="flex justify-between text-[10px] text-slate-400 mt-1">
                <span>Relaxed / Casual</span>
                <span>Moderate</span>
                <span>Spotless / Methodical</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Diet / Food Preference</label>
                <select
                  value={diet}
                  onChange={(e) => setDiet(e.target.value)}
                  className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
                >
                  <option value="pure_veg">Pure Vegetarian</option>
                  <option value="veg_and_egg">Vegetarian + Eggs</option>
                  <option value="omnivore">Non-Vegetarian</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Smoking Habit</label>
                <select
                  value={smoking}
                  onChange={(e) => setSmoking(e.target.value)}
                  className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
                >
                  <option value="never">Non-Smoker (Never)</option>
                  <option value="balcony_only">Social / Balcony Only</option>
                  <option value="regular">Regular Smoker</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Social Battery</label>
                <select
                  value={socialBattery}
                  onChange={(e) => setSocialBattery(e.target.value)}
                  className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
                >
                  <option value="introverted">Quiet / Introverted</option>
                  <option value="balanced">Balanced</option>
                  <option value="extroverted">Social / Lively</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Guests Policy</label>
                <select
                  value={guestsPolicy}
                  onChange={(e) => setGuestsPolicy(e.target.value)}
                  className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white"
                >
                  <option value="rarely">Rarely / No Overnight Guests</option>
                  <option value="occasional_weekends">Occasional Weekends with Notice</option>
                  <option value="open">Open / Friends Welcome</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <p className="text-xs text-slate-500">
              Configure strict non-negotiables. If a candidate violates any strict dealbreaker, they will never be matched with you.
            </p>

            <div className="space-y-3">
              <label className="flex items-start space-x-3 p-3.5 bg-slate-50 rounded-2xl border border-slate-200 cursor-pointer">
                <input
                  type="checkbox"
                  checked={strictSmoking}
                  onChange={(e) => setStrictSmoking(e.target.checked)}
                  className="w-4 h-4 text-indigo-600 rounded mt-0.5"
                />
                <div>
                  <span className="font-bold text-xs text-slate-900 block">Strictly Smoke-Free Household</span>
                  <span className="text-[11px] text-slate-500">
                    No indoor smoking allowed. Zero tolerance for cigarette smoke.
                  </span>
                </div>
              </label>

              <label className="flex items-start space-x-3 p-3.5 bg-slate-50 rounded-2xl border border-slate-200 cursor-pointer">
                <input
                  type="checkbox"
                  checked={strictNonVeg}
                  onChange={(e) => setStrictNonVeg(e.target.checked)}
                  className="w-4 h-4 text-indigo-600 rounded mt-0.5"
                />
                <div>
                  <span className="font-bold text-xs text-slate-900 block">Strictly Pure Vegetarian Kitchen</span>
                  <span className="text-[11px] text-slate-500">
                    No non-veg or meat cooking inside the household kitchen.
                  </span>
                </div>
              </label>

              <label className="flex items-start space-x-3 p-3.5 bg-slate-50 rounded-2xl border border-slate-200 cursor-pointer">
                <input
                  type="checkbox"
                  checked={strictLateNights}
                  onChange={(e) => setStrictLateNights(e.target.checked)}
                  className="w-4 h-4 text-indigo-600 rounded mt-0.5"
                />
                <div>
                  <span className="font-bold text-xs text-slate-900 block">Quiet Hours After 11 PM</span>
                  <span className="text-[11px] text-slate-500">
                    Mandatory peaceful sleep environment during night hours.
                  </span>
                </div>
              </label>
            </div>
          </div>
        )}

        {/* Navigation Buttons */}
        <div className="flex items-center justify-between pt-4 border-t border-slate-100">
          <Button
            variant="outline"
            size="sm"
            disabled={step === 1 || isSubmitting}
            onClick={() => setStep((s) => s - 1)}
            className="gap-1.5"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Previous</span>
          </Button>

          {step < 3 ? (
            <Button
              variant="primary"
              size="sm"
              onClick={() => setStep((s) => s + 1)}
              className="gap-1.5"
            >
              <span>Continue</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          ) : (
            <Button
              variant="primary"
              size="sm"
              isLoading={isSubmitting}
              onClick={handleCompleteOnboarding}
              className="gap-1.5 bg-emerald-600 hover:bg-emerald-700 shadow-md"
            >
              <Check className="w-3.5 h-3.5" />
              <span>Complete Setup & View Matches</span>
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
