"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { PropertyDTO } from "@flatmate/contracts";
import { apiClient } from "@/lib/api-client";
import { formatCurrency, formatDate, formatDateTimeIST } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";
import {
  Button,
  Card,
  Badge,
  Modal,
  Input,
  ImageGallery,
  Skeleton,
  ErrorState,
} from "@flatmate/ui";
import {
  MapPin,
  Bed,
  Bath,
  Sparkles,
  CheckCircle2,
  ShieldCheck,
  Calendar,
  ArrowLeft,
  Video,
  Clock,
  MessageSquare,
  Heart,
  Flag,
  FileCheck,
  AlertTriangle,
  Info,
} from "lucide-react";

export default function PropertyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const propertyId = params.id as string;

  const [property, setProperty] = useState<PropertyDTO | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSaved, setIsSaved] = useState(false);

  // Application Modal state
  const [isApplyModalOpen, setIsApplyModalOpen] = useState(false);
  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(null);
  const [introduction, setIntroduction] = useState("");
  const [proposedRent, setProposedRent] = useState("");
  const [moveInTarget, setMoveInTarget] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [applySuccess, setApplySuccess] = useState(false);

  // Appointment Modal state
  const [isAppointmentModalOpen, setIsAppointmentModalOpen] = useState(false);
  const [appointmentType, setAppointmentType] = useState<"physical_visit" | "video_call">("physical_visit");
  const [appointmentDate, setAppointmentDate] = useState("");
  const [appointmentTime, setAppointmentTime] = useState("11:00");
  const [appointmentNotes, setAppointmentNotes] = useState("");
  const [isSubmittingAppointment, setIsSubmittingAppointment] = useState(false);
  const [appointmentSuccess, setAppointmentSuccess] = useState(false);

  // Report Modal state
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [reportReason, setReportReason] = useState("inaccurate_listing");
  const [reportDescription, setReportDescription] = useState("");
  const [isSubmittingReport, setIsSubmittingReport] = useState(false);
  const [reportSuccess, setReportSuccess] = useState(false);

  useEffect(() => {
    async function loadProperty() {
      try {
        setIsLoading(true);
        setError(null);
        const data = await apiClient<PropertyDTO>(`/properties/${propertyId}`);
        setProperty(data);
        setProposedRent(String(data.monthly_rent));
      } catch (err: any) {
        console.error("Failed to load property:", err);
        setError(err.message || "Failed to load property details");
      } finally {
        setIsLoading(false);
      }
    }
    if (propertyId) loadProperty();

    // Check saved status
    if (typeof window !== "undefined") {
      try {
        const saved = JSON.parse(localStorage.getItem("flatmate_saved_properties") || "[]");
        setIsSaved(saved.includes(propertyId));
      } catch {
        setIsSaved(false);
      }
    }
  }, [propertyId]);

  const toggleSave = () => {
    if (typeof window === "undefined") return;
    try {
      const saved = JSON.parse(localStorage.getItem("flatmate_saved_properties") || "[]");
      let updated: string[];
      if (saved.includes(propertyId)) {
        updated = saved.filter((id: string) => id !== propertyId);
        setIsSaved(false);
      } else {
        updated = [...saved, propertyId];
        setIsSaved(true);
      }
      localStorage.setItem("flatmate_saved_properties", JSON.stringify(updated));
    } catch {
      // Ignored
    }
  };

  const handleApplySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }

    try {
      setIsSubmitting(true);
      await apiClient("/applications", {
        method: "POST",
        body: JSON.stringify({
          property_id: propertyId,
          room_id: selectedRoomId || undefined,
          introduction,
          proposed_rent: parseFloat(proposedRent),
          move_in_target: moveInTarget || new Date().toISOString().split("T")[0],
        }),
      });
      setApplySuccess(true);
      setTimeout(() => {
        setIsApplyModalOpen(false);
        setApplySuccess(false);
      }, 2000);
    } catch (err: any) {
      alert(err.message || "Failed to submit application");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAppointmentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }
    if (!property) return;

    try {
      setIsSubmittingAppointment(true);
      const scheduledIso = new Date(`${appointmentDate}T${appointmentTime}:00Z`).toISOString();
      await apiClient("/appointments/", {
        method: "POST",
        body: JSON.stringify({
          property_id: propertyId,
          room_id: selectedRoomId || undefined,
          host_id: property.owner_id,
          appointment_type: appointmentType,
          scheduled_at: scheduledIso,
          notes: appointmentNotes || undefined,
        }),
      });
      setAppointmentSuccess(true);
      setTimeout(() => {
        setIsAppointmentModalOpen(false);
        setAppointmentSuccess(false);
      }, 2000);
    } catch (err: any) {
      alert(err.message || "Failed to schedule viewing visit");
    } finally {
      setIsSubmittingAppointment(false);
    }
  };

  const handleReportSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }

    try {
      setIsSubmittingReport(true);
      await apiClient("/moderation/reports", {
        method: "POST",
        body: JSON.stringify({
          target_type: "property",
          target_id: propertyId,
          reason: reportReason,
          description: reportDescription || undefined,
        }),
      });
      setReportSuccess(true);
      setTimeout(() => {
        setIsReportModalOpen(false);
        setReportSuccess(false);
        setReportDescription("");
      }, 2000);
    } catch (err: any) {
      alert(err.message || "Failed to submit moderation report");
    } finally {
      setIsSubmittingReport(false);
    }
  };

  const handleEnquireHost = async () => {
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }
    if (!property) return;
    try {
      const res = await apiClient<{ conversation_id: string }>("/messaging/conversations", {
        method: "POST",
        body: JSON.stringify({
          participant_user_ids: [property.owner_id],
          type: "direct",
          property_id: property.id,
        }),
      });
      router.push(`/messages?conversationId=${res.conversation_id}`);
    } catch (err: any) {
      alert(err.message || "Failed to start conversation with host");
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-6">
        <Skeleton variant="text" width="120px" height="24px" />
        <Skeleton variant="rectangular" height="420px" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-4">
            <Skeleton variant="text" width="60%" height="36px" />
            <Skeleton variant="text" width="100%" height="80px" />
          </div>
          <Skeleton variant="card" height="320px" />
        </div>
      </div>
    );
  }

  if (error || !property) {
    return (
      <div className="max-w-xl mx-auto px-4 py-20 text-center">
        <ErrorState
          title="Property Not Found"
          message={error || "The property listing you requested could not be located or may have been unlisted."}
          onRetry={() => router.push("/properties")}
        />
      </div>
    );
  }

  const currency = property.currency || "INR";
  const displayAddress =
    property.address_display || (property.city ? `${property.city}` : "India");
  const depositAmount = property.security_deposit ?? 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Back & Action Row */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => router.back()}
          className="inline-flex items-center text-xs font-semibold text-charcoal-muted hover:text-forest transition-colors"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          <span>Back to Listings</span>
        </button>

        <div className="flex items-center space-x-2">
          {/* Save / Favorite Toggle */}
          <button
            onClick={toggleSave}
            className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all ${
              isSaved
                ? "bg-rose-50 border-rose-200 text-rose-600"
                : "bg-white border-warm-200 text-charcoal hover:bg-slate-50"
            }`}
          >
            <Heart className={`w-4 h-4 ${isSaved ? "fill-rose-500 text-rose-500" : ""}`} />
            <span>{isSaved ? "Saved" : "Save"}</span>
          </button>

          {/* Report Property */}
          <button
            onClick={() => setIsReportModalOpen(true)}
            className="p-1.5 text-charcoal-muted hover:text-rose-600 rounded-lg hover:bg-rose-50 transition-colors"
            title="Report this listing"
          >
            <Flag className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Property Image Gallery (Thumbnails & Fullscreen Lightbox) */}
      <ImageGallery
        images={property.images || []}
        alt={property.title}
        className="shadow-sm border border-warm-200"
      />

      {/* Main Details & Pricing Sticky Box */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Property Specs & Rooms */}
        <div className="lg:col-span-2 space-y-8">
          <div>
            <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
              <div className="flex items-center space-x-1.5 text-xs text-charcoal-muted">
                <MapPin className="w-4 h-4 text-forest" />
                <span>
                  {displayAddress} {property.postal_code ? `• ${property.postal_code}` : ""}
                </span>
              </div>
              <div className="flex items-center space-x-1.5">
                {property.is_verified && (
                  <Badge variant="forest" size="sm" className="gap-1">
                    <ShieldCheck className="w-3.5 h-3.5 text-pale-green" /> Verified Listing
                  </Badge>
                )}
                <Badge variant="warm" size="sm" className="capitalize">
                  {property.property_category?.replace(/_/g, " ")}
                </Badge>
              </div>
            </div>

            <h1 className="text-3xl font-extrabold text-charcoal tracking-tight">
              {property.title}
            </h1>

            {/* DPDP Location Notice */}
            <div className="mt-3 text-xs bg-warm-50 p-3 rounded-xl border border-warm-200 flex items-start space-x-2">
              <Info className="w-4 h-4 text-forest shrink-0 mt-0.5" />
              <div className="text-charcoal-muted leading-relaxed">
                <strong className="text-charcoal font-semibold">Exact Address Status: </strong>
                {property.address_exact || "[Exact door and building number protected until viewing visit is confirmed]"}
              </div>
            </div>

            <div className="flex flex-wrap gap-4 mt-5 pt-4 border-t border-slate-100 text-sm text-charcoal">
              <div className="flex items-center space-x-1.5">
                <Bed className="w-4 h-4 text-forest" />
                <span className="font-semibold">{property.total_bedrooms} Bedrooms</span>
              </div>
              <div className="flex items-center space-x-1.5">
                <Bath className="w-4 h-4 text-forest" />
                <span className="font-semibold">{property.total_bathrooms} Bathrooms</span>
              </div>
              <div className="flex items-center space-x-1.5">
                <Calendar className="w-4 h-4 text-forest" />
                <span>Available From {formatDate(property.available_from)}</span>
              </div>
            </div>
          </div>

          {/* Description */}
          <div>
            <h3 className="text-lg font-bold text-charcoal mb-2">About the Property</h3>
            <p className="text-sm text-charcoal-muted leading-relaxed whitespace-pre-line">
              {property.description}
            </p>
          </div>

          {/* Financials & Rules Summary */}
          <div className="p-5 bg-warm-50/60 rounded-2xl border border-warm-200 space-y-3">
            <h3 className="text-sm font-bold text-charcoal uppercase tracking-wider">
              Financial & Lease Details
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs">
              <div>
                <span className="text-charcoal-muted block">Monthly Rent</span>
                <span className="font-bold text-charcoal text-sm">
                  {formatCurrency(property.monthly_rent, currency)}
                </span>
              </div>
              <div>
                <span className="text-charcoal-muted block">Security Deposit</span>
                <span className="font-bold text-charcoal text-sm">
                  {formatCurrency(depositAmount, currency)}
                </span>
              </div>
              <div>
                <span className="text-charcoal-muted block">Utilities & Bills</span>
                <span className="font-semibold text-charcoal">
                  {property.bills_included ? "Included in rent" : "Billed separately"}
                </span>
              </div>
              <div>
                <span className="text-charcoal-muted block">Furnishing</span>
                <span className="font-semibold text-charcoal capitalize">
                  {property.furnishing_status?.replace(/_/g, " ") || "Semi-Furnished"}
                </span>
              </div>
              <div>
                <span className="text-charcoal-muted block">Pets</span>
                <span className="font-semibold text-charcoal">
                  {property.pets_allowed ? "Allowed" : "Not permitted"}
                </span>
              </div>
              <div>
                <span className="text-charcoal-muted block">Smoking</span>
                <span className="font-semibold text-charcoal">
                  {property.smoking_allowed ? "Permitted" : "Strictly prohibited"}
                </span>
              </div>
            </div>
          </div>

          {/* Individual Rooms & Beds Inventory */}
          {property.rooms && property.rooms.length > 0 && (
            <div>
              <h3 className="text-lg font-bold text-charcoal mb-3">
                Available Rooms in this Flat
              </h3>
              <div className="space-y-3">
                {property.rooms.map((room) => (
                  <div
                    key={room.id}
                    className="p-4 bg-white rounded-2xl border border-warm-200 flex items-center justify-between shadow-2xs"
                  >
                    <div>
                      <h4 className="font-bold text-charcoal text-sm">{room.room_name}</h4>
                      <p className="text-xs text-charcoal-muted mt-0.5">
                        {room.private_bath ? "Private En-Suite Bath" : "Shared Bath"} • Available from {formatDate(room.available_from)}
                      </p>
                      {room.beds && room.beds.length > 0 && (
                        <p className="text-[11px] text-secondary-green font-medium mt-1">
                          {room.beds.filter((b) => b.is_occupied).length} of {room.beds.length} beds occupied
                        </p>
                      )}
                    </div>
                    <div className="flex items-center space-x-3">
                      <span className="font-bold text-charcoal text-sm">
                        {formatCurrency(room.room_rent, currency)}/mo
                      </span>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          setSelectedRoomId(room.id);
                          setProposedRent(String(room.room_rent));
                          setIsApplyModalOpen(true);
                        }}
                      >
                        Apply for Room
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Included Amenities */}
          {property.amenities && property.amenities.length > 0 && (
            <div>
              <h3 className="text-lg font-bold text-charcoal mb-3">Included Amenities</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                {property.amenities.map((amenity) => (
                  <div
                    key={amenity}
                    className="flex items-center space-x-2 text-xs font-medium text-charcoal bg-warm-50 px-3.5 py-2.5 rounded-xl border border-warm-200"
                  >
                    <CheckCircle2 className="w-4 h-4 text-forest shrink-0" />
                    <span className="capitalize">{amenity.replace(/_/g, " ")}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right Sticky Column: Actions & Booking */}
        <div>
          <Card className="p-6 sticky top-24 border-warm-200 shadow-md space-y-6 bg-white">
            <div>
              <span className="text-xs text-charcoal-muted font-medium">Monthly Rent</span>
              <div className="text-3xl font-extrabold text-charcoal">
                {formatCurrency(property.monthly_rent, currency)}
                <span className="text-sm font-normal text-charcoal-muted"> /month</span>
              </div>
              <p className="text-xs text-charcoal-muted mt-1">
                Security Deposit: {formatCurrency(depositAmount, currency)}
              </p>
            </div>

            <div className="space-y-3">
              <Button
                variant="primary"
                size="lg"
                className="w-full shadow-sm justify-center py-3.5"
                onClick={() => {
                  setSelectedRoomId(null);
                  setProposedRent(String(property.monthly_rent));
                  setIsApplyModalOpen(true);
                }}
              >
                Apply for Accommodation
              </Button>

              <Button
                variant="outline"
                size="md"
                className="w-full gap-2 justify-center"
                onClick={() => {
                  setSelectedRoomId(null);
                  setIsAppointmentModalOpen(true);
                }}
              >
                <Calendar className="w-4 h-4 text-forest" />
                <span>Schedule Viewing Visit</span>
              </Button>

              <Button
                variant="ghost"
                size="md"
                className="w-full gap-2 text-forest hover:bg-pale-green/30 justify-center"
                onClick={handleEnquireHost}
              >
                <MessageSquare className="w-4 h-4" />
                <span>Direct Message Host</span>
              </Button>
            </div>

            {/* Scam Warning in Box */}
            <div className="pt-4 border-t border-slate-100 space-y-2 text-xs text-charcoal-muted">
              <div className="flex items-center space-x-2 text-forest font-semibold">
                <ShieldCheck className="w-4 h-4" />
                <span>Protected by Flatmate</span>
              </div>
              <p className="leading-relaxed">
                Never pay advance token money before an in-person viewing. Keep all communications on-platform.
              </p>
            </div>
          </Card>
        </div>
      </div>

      {/* Tenancy Application Modal */}
      <Modal
        isOpen={isApplyModalOpen}
        onClose={() => setIsApplyModalOpen(false)}
        title="Submit Tenancy Application"
        description="Introduce yourself to the landlord and submit your proposed move-in terms."
      >
        {applySuccess ? (
          <div className="text-center py-6">
            <CheckCircle2 className="w-12 h-12 text-forest mx-auto mb-2" />
            <h4 className="font-bold text-charcoal text-base">Application Submitted!</h4>
            <p className="text-xs text-charcoal-muted mt-1">
              The owner has been notified. You can track this in My Space.
            </p>
          </div>
        ) : (
          <form onSubmit={handleApplySubmit} className="space-y-4 mt-2">
            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1">
                Introduction to the Landlord
              </label>
              <textarea
                required
                rows={4}
                value={introduction}
                onChange={(e) => setIntroduction(e.target.value)}
                placeholder="Tell them about your profession, lifestyle, work hours, and why this flat suits you..."
                className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>

            <Input
              label={`Proposed Monthly Rent (${currency})`}
              type="number"
              required
              value={proposedRent}
              onChange={(e) => setProposedRent(e.target.value)}
            />

            <Input
              label="Intended Move-In Date"
              type="date"
              required
              value={moveInTarget}
              onChange={(e) => setMoveInTarget(e.target.value)}
            />

            <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isSubmitting}>
              Submit Application Dossier
            </Button>
          </form>
        )}
      </Modal>

      {/* Viewing Visit Appointment Modal */}
      <Modal
        isOpen={isAppointmentModalOpen}
        onClose={() => setIsAppointmentModalOpen(false)}
        title="Schedule Property Viewing"
        description="Book a physical visit or virtual video tour with the host."
      >
        {appointmentSuccess ? (
          <div className="text-center py-6">
            <CheckCircle2 className="w-12 h-12 text-forest mx-auto mb-2" />
            <h4 className="font-bold text-charcoal text-base">Viewing Visit Requested!</h4>
            <p className="text-xs text-charcoal-muted mt-1">
              The host will review your requested time slot. Once confirmed, exact directions will unlock.
            </p>
          </div>
        ) : (
          <form onSubmit={handleAppointmentSubmit} className="space-y-4 mt-2">
            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1.5">
                Inspection Type
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setAppointmentType("physical_visit")}
                  className={`py-2 px-3 text-xs font-semibold rounded-xl border flex items-center justify-center gap-1.5 transition-all ${
                    appointmentType === "physical_visit"
                      ? "bg-pale-green/40 border-forest text-forest shadow-2xs"
                      : "border-slate-200 text-charcoal hover:bg-slate-50"
                  }`}
                >
                  <MapPin className="w-3.5 h-3.5" />
                  <span>Physical Visit</span>
                </button>
                <button
                  type="button"
                  onClick={() => setAppointmentType("video_call")}
                  className={`py-2 px-3 text-xs font-semibold rounded-xl border flex items-center justify-center gap-1.5 transition-all ${
                    appointmentType === "video_call"
                      ? "bg-pale-green/40 border-forest text-forest shadow-2xs"
                      : "border-slate-200 text-charcoal hover:bg-slate-50"
                  }`}
                >
                  <Video className="w-3.5 h-3.5" />
                  <span>Video Call</span>
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Preferred Date"
                type="date"
                required
                value={appointmentDate}
                onChange={(e) => setAppointmentDate(e.target.value)}
              />
              <Input
                label="Preferred Time (IST)"
                type="time"
                required
                value={appointmentTime}
                onChange={(e) => setAppointmentTime(e.target.value)}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1">
                Notes for Host (Optional)
              </label>
              <textarea
                rows={2}
                value={appointmentNotes}
                onChange={(e) => setAppointmentNotes(e.target.value)}
                placeholder="e.g. Would like to see the kitchen and verify power backup."
                className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              className="w-full mt-2"
              isLoading={isSubmittingAppointment}
            >
              Request Viewing Visit
            </Button>
          </form>
        )}
      </Modal>

      {/* Report Property Modal */}
      <Modal
        isOpen={isReportModalOpen}
        onClose={() => setIsReportModalOpen(false)}
        title="Report This Property"
        description="Help us maintain a safe marketplace. Reports are reviewed by human moderators."
      >
        {reportSuccess ? (
          <div className="text-center py-6">
            <CheckCircle2 className="w-12 h-12 text-forest mx-auto mb-2" />
            <h4 className="font-bold text-charcoal text-base">Report Submitted</h4>
            <p className="text-xs text-charcoal-muted mt-1">
              Thank you for keeping our community safe. Our team is investigating.
            </p>
          </div>
        ) : (
          <form onSubmit={handleReportSubmit} className="space-y-4 mt-2">
            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1">
                Reason for Report
              </label>
              <select
                value={reportReason}
                onChange={(e) => setReportReason(e.target.value)}
                className="w-full text-xs font-semibold border border-slate-300 rounded-xl px-3.5 py-2.5 bg-white text-charcoal focus:ring-2 focus:ring-brand-500"
              >
                <option value="inaccurate_listing">Inaccurate Photos or Information</option>
                <option value="scam_or_fraud">Asked for Advance Payment / Scam</option>
                <option value="duplicate_listing">Duplicate Listing</option>
                <option value="unavailable_unit">Unit Already Rented / Not Available</option>
                <option value="inappropriate_conduct">Unprofessional or Harassing Conduct</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-charcoal mb-1">
                Additional Details
              </label>
              <textarea
                required
                rows={3}
                value={reportDescription}
                onChange={(e) => setReportDescription(e.target.value)}
                placeholder="Please describe what occurred or what seems suspicious..."
                className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>

            <Button
              type="submit"
              variant="danger"
              className="w-full mt-2"
              isLoading={isSubmittingReport}
            >
              Submit Moderation Report
            </Button>
          </form>
        )}
      </Modal>
    </div>
  );
}
