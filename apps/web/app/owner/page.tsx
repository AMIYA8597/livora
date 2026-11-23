"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useApiQuery } from "@/hooks/useApiQuery";
import { PageLoading } from "@/components/states/PageLoading";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api-client";
import { PropertyInventoryForm } from "@/features/properties/components/PropertyInventoryForm";
import { Card, Button, Badge, Modal, Avatar, EmptyState, ErrorState } from "@flatmate/ui";
import { formatCurrency, formatIndianCompactCurrency, formatDate, formatDateTimeIST } from "@/lib/utils";
import {
  Building,
  Users,
  CheckCircle2,
  XCircle,
  Plus,
  Home,
  IndianRupee,
  Clock,
  Check,
  X,
  FileText,
  Calendar,
  Layers,
  Bed,
  Eye,
  PauseCircle,
  PlayCircle,
  MapPin,
  Sparkles,
} from "lucide-react";

interface BedInfo {
  id: string;
  bed_identifier: string;
  monthly_rent: number;
  is_occupied: boolean;
  current_occupant_id?: string | null;
}

interface RoomInfo {
  id: string;
  room_name: string;
  room_type: string;
  room_rent: number;
  deposit: number;
  private_bath: boolean;
  beds: BedInfo[];
}

interface OwnerProperty {
  id: string;
  title: string;
  description: string;
  property_category: string;
  configuration: string;
  address_display: string;
  city: string;
  monthly_rent: number;
  security_deposit: number;
  listing_status: string;
  is_verified: boolean;
  is_active: boolean;
  rooms: RoomInfo[];
}

interface ApplicantCard {
  application?: {
    id: string;
    proposed_rent: number;
    move_in_target: string;
    status: string;
    introduction?: string;
  };
  application_id?: string;
  applicant_name: string;
  applicant_email: string;
  applicant_occupation?: string | null;
  property_title: string;
  proposed_rent?: number;
  move_in_target?: string;
  status?: string;
}

interface AppointmentItem {
  id: string;
  property_id: string;
  applicant_id: string;
  host_id: string;
  scheduled_at: string;
  status: string;
  notes?: string;
}

export default function OwnerPortalPage() {
  const { isAuthenticated, isLoading: authLoading, isOwner, isAdmin, user } = useAuth();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"overview" | "properties" | "applications" | "appointments">("overview");

  const statsQuery = useApiQuery<any>(isAuthenticated ? "/owners/dashboard" : null);
  const applicationsQuery = useApiQuery<ApplicantCard[]>(isAuthenticated ? "/owners/applications" : null);
  const propertiesQuery = useApiQuery<OwnerProperty[]>(isAuthenticated ? "/owners/properties" : null);
  const appointmentsQuery = useApiQuery<AppointmentItem[]>(isAuthenticated ? "/appointments" : null);
  const stats = statsQuery.data ?? null;
  const properties = propertiesQuery.data ?? [];
  const applications = applicationsQuery.data ?? [];
  const appointments = appointmentsQuery.data ?? [];
  const setProperties = propertiesQuery.setData;
  const setApplications = applicationsQuery.setData;
  const setAppointments = appointmentsQuery.setData;
  const isLoading =
    statsQuery.isLoading || applicationsQuery.isLoading || propertiesQuery.isLoading || appointmentsQuery.isLoading;
  const loadError = statsQuery.error || applicationsQuery.error || propertiesQuery.error || appointmentsQuery.error;
  const loadOwnerData = () => {
    statsQuery.refetch();
    applicationsQuery.refetch();
    propertiesQuery.refetch();
    appointmentsQuery.refetch();
  };
  const [isListingModalOpen, setIsListingModalOpen] = useState(false);
  const [isSubmittingProperty, setIsSubmittingProperty] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [selectedPropertyRooms, setSelectedPropertyRooms] = useState<OwnerProperty | null>(null);

  const handleToggleListingStatus = async (propertyId: string, currentStatus: string) => {
    const nextStatus = currentStatus === "published" ? "paused" : "published";
    try {
      await apiClient(`/properties/${propertyId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ listing_status: nextStatus }),
      });
      setProperties((prev = []) =>
        prev.map((p) => (p.id === propertyId ? { ...p, listing_status: nextStatus, is_active: nextStatus === "published" } : p))
      );
      setActionNotice(`Property listing status updated to ${nextStatus}.`);
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to update listing status");
    }
  };

  const handleVacateBed = async (bedId: string) => {
    try {
      await apiClient(`/properties/beds/${bedId}/vacate`, { method: "POST" });
      setActionNotice("Bed slot marked as vacant and available.");
      setTimeout(() => setActionNotice(null), 3000);
      loadOwnerData();
    } catch (err: any) {
      alert(err.message || "Failed to vacate bed");
    }
  };

  const handleUpdateApplicationStatus = async (appId: string, newStatus: "accepted" | "rejected") => {
    try {
      await apiClient(`/applications/${appId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
      setApplications((prev = []) =>
        prev.map((a) => {
          const currentId = a.application?.id || a.application_id;
          if (currentId === appId) {
            if (a.application) {
              return { ...a, application: { ...a.application, status: newStatus } };
            }
            return { ...a, status: newStatus };
          }
          return a;
        })
      );
      setActionNotice(`Application marked as ${newStatus}.`);
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to update application status");
    }
  };

  const handleUpdateAppointmentStatus = async (apptId: string, newStatus: "confirmed" | "cancelled") => {
    try {
      await apiClient(`/appointments/${apptId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
      setAppointments((prev = []) =>
        prev.map((a) => (a.id === apptId ? { ...a, status: newStatus } : a))
      );
      setActionNotice(`Viewing appointment marked as ${newStatus}.`);
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to update appointment status");
    }
  };

  const handleCreateProperty = async (propertyData: any) => {
    try {
      setIsSubmittingProperty(true);
      await apiClient("/properties", {
        method: "POST",
        body: JSON.stringify({
          title: `${propertyData.configuration} in ${propertyData.address_display}`,
          description: `Spacious, verified ${propertyData.configuration} managed by verified landlord. Available from ${propertyData.available_from}.`,
          property_category: propertyData.property_category,
          configuration: propertyData.configuration,
          latitude: 12.9716,
          longitude: 77.5946,
          address_display: propertyData.address_display,
          address_exact: propertyData.address_exact,
          city: propertyData.city,
          postal_code: propertyData.postal_code,
          country: "India",
          currency: "INR",
          monthly_rent: propertyData.monthly_rent,
          security_deposit: propertyData.security_deposit,
          maintenance_monthly: propertyData.maintenance_monthly,
          total_bedrooms: parseInt(propertyData.configuration[0], 10) || 2,
          total_bathrooms: 2,
          available_from: propertyData.available_from,
          is_furnished: false,
          furnishing_status: "semi_furnished",
          pets_allowed: false,
          smoking_allowed: propertyData.smoking_allowed,
          images: ["https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800"],
          amenities: ["wifi", "power_backup", "security", "lift"],
          rooms: propertyData.rooms,
        }),
      });
      setIsListingModalOpen(false);
      setActionNotice("Property listed successfully! It is now live in search.");
      setTimeout(() => setActionNotice(null), 4000);
      loadOwnerData();
    } catch (err: any) {
      alert(err.message || "Failed to list property");
    } finally {
      setIsSubmittingProperty(false);
    }
  };

  if (authLoading) return <PageLoading />;

  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto py-20 px-4 text-center">
        <Card className="p-8">
          <Building className="w-12 h-12 text-forest mx-auto mb-3" />
          <h2 className="text-xl font-bold text-charcoal mb-2">Landlord & Owner Portal</h2>
          <p className="text-xs text-charcoal-muted mb-6">Sign in with an owner or landlord account to manage your listings.</p>
          <Button variant="primary" onClick={() => router.push("/login")} className="w-full">
            Sign In
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 bg-forest-pale text-forest text-xs font-semibold px-3 py-1 rounded-full mb-2">
            <Building className="w-3.5 h-3.5" />
            <span>Owner & Landlord Operations</span>
          </div>
          <h1 className="text-3xl font-extrabold text-charcoal tracking-tight">Landlord Dashboard</h1>
          <p className="text-charcoal-muted text-sm mt-1">
            Real-time management of properties, inventory availability, tenancy applications, and visits.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <Link href="/owner/listings/create">
            <Button variant="outline" size="md" className="gap-2">
              <Sparkles className="w-4 h-4 text-forest" />
              <span>Listing Wizard</span>
            </Button>
          </Link>
          <Button variant="primary" size="md" className="gap-2 shadow-sm" onClick={() => setIsListingModalOpen(true)}>
            <Plus className="w-4 h-4" />
            <span>Quick Add Property</span>
          </Button>
        </div>
      </div>

      {loadError && !isLoading && (
        <ErrorState title="Some portal data failed to load" message={loadError.message} onRetry={loadOwnerData} />
      )}

      {actionNotice && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-2xl text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <Card className="p-4 border-slate-200/80 bg-white shadow-xs">
          <span className="text-[11px] font-semibold text-charcoal-muted uppercase block">Total Properties</span>
          <span className="text-2xl font-black text-charcoal mt-1 block">
            {stats ? stats.total_properties : properties.length}
          </span>
          <span className="text-[10px] text-charcoal-muted mt-0.5 block">Managed on platform</span>
        </Card>

        <Card className="p-4 border-slate-200/80 bg-white shadow-xs">
          <span className="text-[11px] font-semibold text-charcoal-muted uppercase block">Active Listings</span>
          <span className="text-2xl font-black text-forest mt-1 block">
            {stats ? stats.active_listings : properties.filter((p) => p.is_active).length}
          </span>
          <span className="text-[10px] text-forest/80 mt-0.5 block">Live in search</span>
        </Card>

        <Card className="p-4 border-slate-200/80 bg-white shadow-xs">
          <span className="text-[11px] font-semibold text-charcoal-muted uppercase block">Pending Applications</span>
          <span className="text-2xl font-black text-amber-600 mt-1 block">
            {stats?.pending_applications ?? applications.length}
          </span>
          <span className="text-[10px] text-amber-600/80 mt-0.5 block">Requires review</span>
        </Card>

        <Card className="p-4 border-slate-200/80 bg-white shadow-xs">
          <span className="text-[11px] font-semibold text-charcoal-muted uppercase block">Scheduled Visits</span>
          <span className="text-2xl font-black text-blue-600 mt-1 block">
            {appointments.length}
          </span>
          <span className="text-[10px] text-blue-600/80 mt-0.5 block">Viewing requests</span>
        </Card>

        <Card className="p-4 border-slate-200/80 bg-white shadow-xs col-span-2 sm:col-span-1">
          <span className="text-[11px] font-semibold text-charcoal-muted uppercase block">Estimated Revenue</span>
          <span className="text-2xl font-black text-charcoal mt-1 block">
            {formatIndianCompactCurrency(stats?.estimated_monthly_revenue ? Number(stats.estimated_monthly_revenue) : 0)}
          </span>
          <span className="text-[10px] text-charcoal-muted mt-0.5 block">Contracted monthly</span>
        </Card>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-slate-200 space-x-6 text-sm font-semibold">
        <button
          onClick={() => setActiveTab("overview")}
          className={`pb-3 transition-colors ${
            activeTab === "overview"
              ? "border-b-2 border-forest text-forest font-bold"
              : "text-charcoal-muted hover:text-charcoal"
          }`}
        >
          Properties Inventory ({properties.length})
        </button>
        <button
          onClick={() => setActiveTab("applications")}
          className={`pb-3 transition-colors ${
            activeTab === "applications"
              ? "border-b-2 border-forest text-forest font-bold"
              : "text-charcoal-muted hover:text-charcoal"
          }`}
        >
          Tenancy Applications ({applications.length})
        </button>
        <button
          onClick={() => setActiveTab("appointments")}
          className={`pb-3 transition-colors ${
            activeTab === "appointments"
              ? "border-b-2 border-forest text-forest font-bold"
              : "text-charcoal-muted hover:text-charcoal"
          }`}
        >
          Viewing Visits ({appointments.length})
        </button>
      </div>

      {/* Tab 1: Properties & Room Inventory */}
      {activeTab === "overview" && (
        <div className="space-y-4">
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2].map((i) => (
                <div key={i} className="h-32 bg-slate-100 rounded-2xl animate-pulse" />
              ))}
            </div>
          ) : properties.length === 0 ? (
            <EmptyState
              title="No properties listed yet"
              description="Register your rental accommodations, flats, or PGs to start receiving verified tenant applications."
              actionLabel="Add Your First Property"
              onAction={() => setIsListingModalOpen(true)}
            />
          ) : (
            <div className="space-y-4">
              {properties.map((prop) => (
                <Card key={prop.id} className="p-5 border-slate-200/80 space-y-4">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-bold text-charcoal text-base">{prop.title}</h3>
                        <Badge variant={prop.is_active ? "success" : "default"}>
                          {prop.listing_status || (prop.is_active ? "published" : "paused")}
                        </Badge>
                        {prop.is_verified && <Badge variant="forest">Verified</Badge>}
                      </div>
                      <p className="text-xs text-charcoal-muted mt-1 flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5" />
                        <span>{prop.address_display}, {prop.city}</span>
                        <span className="mx-1">•</span>
                        <span className="font-semibold text-charcoal">{formatCurrency(prop.monthly_rent, "INR")}/mo</span>
                        <span className="mx-1">•</span>
                        <span>Deposit: {formatCurrency(prop.security_deposit, "INR")}</span>
                      </p>
                    </div>

                    <div className="flex items-center space-x-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="gap-1.5"
                        onClick={() => handleToggleListingStatus(prop.id, prop.listing_status)}
                      >
                        {prop.is_active ? (
                          <>
                            <PauseCircle className="w-3.5 h-3.5 text-amber-600" />
                            <span>Pause Listing</span>
                          </>
                        ) : (
                          <>
                            <PlayCircle className="w-3.5 h-3.5 text-forest" />
                            <span>Publish Listing</span>
                          </>
                        )}
                      </Button>
                      <Link href={`/properties/${prop.id}`}>
                        <Button size="sm" variant="ghost" className="gap-1">
                          <Eye className="w-3.5 h-3.5" />
                          <span>View Public Page</span>
                        </Button>
                      </Link>
                    </div>
                  </div>

                  {/* Rooms and Beds Details */}
                  {prop.rooms && prop.rooms.length > 0 && (
                    <div className="pt-3 border-t border-slate-100 space-y-2">
                      <span className="text-xs font-semibold text-charcoal block">Room & Bed Inventory Availability:</span>
                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                        {prop.rooms.map((room) => (
                          <div key={room.id} className="p-3 bg-warm rounded-xl border border-slate-200/60 text-xs">
                            <div className="flex items-center justify-between font-semibold text-charcoal">
                              <span>{room.room_name}</span>
                              <span className="text-forest">{formatCurrency(room.room_rent, "INR")}/mo</span>
                            </div>
                            <div className="mt-2 space-y-1">
                              {room.beds && room.beds.map((bed) => (
                                <div key={bed.id} className="flex items-center justify-between text-[11px] text-charcoal-muted">
                                  <span>{bed.bed_identifier}</span>
                                  <div className="flex items-center gap-1.5">
                                    <Badge variant={bed.is_occupied ? "warning" : "success"} size="sm">
                                      {bed.is_occupied ? "Occupied" : "Vacant"}
                                    </Badge>
                                    {bed.is_occupied && (
                                      <button
                                        type="button"
                                        onClick={() => handleVacateBed(bed.id)}
                                        className="text-forest font-bold hover:underline"
                                      >
                                        Vacate
                                      </button>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Tenancy Applications */}
      {activeTab === "applications" && (
        <div className="space-y-4">
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2].map((i) => (
                <div key={i} className="h-28 bg-slate-100 rounded-2xl animate-pulse" />
              ))}
            </div>
          ) : applications.length === 0 ? (
            <EmptyState
              title="No pending tenancy applications"
              description="When seekers apply for your listings, their profile background and compatibility details will appear here."
            />
          ) : (
            <div className="space-y-3">
              {applications.map((app) => {
                const appId = app.application?.id || app.application_id || "";
                const appStatus = app.application?.status || app.status || "submitted";
                const propRent = app.application?.proposed_rent || app.proposed_rent || 0;
                const moveIn = app.application?.move_in_target || app.move_in_target || "";

                return (
                  <Card key={appId} className="p-5 border-slate-200/80 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                    <div className="flex items-start space-x-4">
                      <Avatar alt={app.applicant_name} size="md" isVerified={true} />
                      <div>
                        <div className="flex items-center space-x-2">
                          <h4 className="font-bold text-charcoal text-sm">{app.applicant_name}</h4>
                          <Badge
                            variant={
                              appStatus === "accepted" || appStatus === "approved"
                                ? "success"
                                : appStatus === "rejected"
                                ? "danger"
                                : "warning"
                            }
                            className="capitalize"
                          >
                            {appStatus}
                          </Badge>
                        </div>
                        <p className="text-xs text-charcoal mt-1">
                          Applying for: <span className="font-semibold">{app.property_title}</span>
                          {app.applicant_occupation && <span> • {app.applicant_occupation}</span>}
                        </p>
                        <p className="text-xs text-charcoal-muted mt-0.5">
                          Offered Rent: <span className="font-semibold text-charcoal">{formatCurrency(propRent, "INR")}</span> • Target Move-in: {formatDate(moveIn)}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center space-x-2 self-end md:self-center">
                      {appStatus === "submitted" || appStatus === "reviewing" || appStatus === "pending" ? (
                        <>
                          <Button
                            size="sm"
                            variant="primary"
                            className="gap-1 bg-forest hover:bg-forest-secondary"
                            onClick={() => handleUpdateApplicationStatus(appId, "accepted")}
                          >
                            <Check className="w-3.5 h-3.5" />
                            <span>Accept</span>
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-1 text-rose-600 hover:bg-rose-50 border-rose-200"
                            onClick={() => handleUpdateApplicationStatus(appId, "rejected")}
                          >
                            <X className="w-3.5 h-3.5" />
                            <span>Decline</span>
                          </Button>
                        </>
                      ) : (
                        <span className="text-xs font-semibold text-charcoal-muted capitalize">Decision: {appStatus}</span>
                      )}
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Viewing Visits */}
      {activeTab === "appointments" && (
        <div className="space-y-4">
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2].map((i) => (
                <div key={i} className="h-24 bg-slate-100 rounded-2xl animate-pulse" />
              ))}
            </div>
          ) : appointments.length === 0 ? (
            <EmptyState
              title="No scheduled viewing appointments"
              description="When verified seekers request a physical property visit, the schedule will appear here."
            />
          ) : (
            <div className="space-y-3">
              {appointments.map((appt) => (
                <Card key={appt.id} className="p-4 border-slate-200/80 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-charcoal text-sm">
                        Viewing Appointment
                      </span>
                      <Badge
                        variant={appt.status === "confirmed" ? "success" : appt.status === "cancelled" ? "danger" : "warning"}
                        className="capitalize"
                      >
                        {appt.status}
                      </Badge>
                    </div>
                    <p className="text-xs text-charcoal-muted mt-1 flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-forest" />
                      <span>{formatDateTimeIST(appt.scheduled_at)}</span>
                    </p>
                    {appt.notes && <p className="text-xs text-charcoal-muted mt-1 italic">&ldquo;{appt.notes}&rdquo;</p>}
                  </div>

                  <div className="flex items-center space-x-2">
                    {appt.status === "pending" && (
                      <>
                        <Button
                          size="sm"
                          variant="primary"
                          className="gap-1 bg-forest hover:bg-forest-secondary text-xs"
                          onClick={() => handleUpdateAppointmentStatus(appt.id, "confirmed")}
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>Confirm</span>
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="gap-1 text-rose-600 border-rose-200 text-xs"
                          onClick={() => handleUpdateAppointmentStatus(appt.id, "cancelled")}
                        >
                          <X className="w-3.5 h-3.5" />
                          <span>Cancel</span>
                        </Button>
                      </>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Listing Creation Modal with PropertyInventoryForm */}
      <Modal
        isOpen={isListingModalOpen}
        onClose={() => setIsListingModalOpen(false)}
        title="List New Property / Unit"
        description="Add a verified accommodation unit to your rental inventory."
      >
        <PropertyInventoryForm onSubmit={handleCreateProperty} isLoading={isSubmittingProperty} />
      </Modal>
    </div>
  );
}
