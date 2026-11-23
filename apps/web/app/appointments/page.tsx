"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { useApiQuery } from "@/hooks/useApiQuery";
import { apiClient } from "@/lib/api-client";
import { AppointmentDTO } from "@flatmate/contracts";
import { Card, Button, Badge, Modal, ErrorState } from "@flatmate/ui";
import { PageLoading } from "@/components/states/PageLoading";
import { formatDateTimeIST, formatDate } from "@/lib/utils";
import {
  Calendar,
  Clock,
  MapPin,
  Video,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  User,
  Check,
  X,
  Building,
} from "lucide-react";

export default function AppointmentsPage() {
  const { isAuthenticated, isLoading: authLoading, user } = useAuth();
  const appointmentsQuery = useApiQuery<AppointmentDTO[]>(isAuthenticated ? "/appointments/" : null);
  const appointments = appointmentsQuery.data ?? [];
  const setAppointments = appointmentsQuery.setData;
  const isLoading = appointmentsQuery.isLoading;
  const [activeTab, setActiveTab] = useState<"upcoming" | "past" | "requests">("upcoming");
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const handleUpdateStatus = async (
    apptId: string,
    newStatus: "confirmed" | "rejected" | "cancelled"
  ) => {
    try {
      await apiClient(`/appointments/${apptId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
      setAppointments((prev = []) =>
        prev.map((a) => (a.id === apptId ? { ...a, status: newStatus } : a))
      );
      setActionNotice(`Appointment status updated to ${newStatus}.`);
      setTimeout(() => setActionNotice(null), 3000);
      appointmentsQuery.refetch();
    } catch (err: any) {
      alert(err.message || "Failed to update appointment");
    }
  };

  const now = new Date();
  const upcomingList = appointments.filter((a) => new Date(a.scheduled_at) >= now && a.status !== "cancelled" && a.status !== "rejected");
  const pastList = appointments.filter((a) => new Date(a.scheduled_at) < now || a.status === "cancelled" || a.status === "rejected");
  const requestsList = appointments.filter((a) => a.host_id === user?.id && a.status === "requested");

  const currentDisplayList =
    activeTab === "upcoming" ? upcomingList : activeTab === "past" ? pastList : requestsList;

  if (authLoading) return <PageLoading />;

  if (!isAuthenticated) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <Calendar className="w-12 h-12 text-indigo-600 mx-auto mb-3" />
        <h2 className="text-xl font-bold text-slate-900">Please sign in to view your scheduled visits</h2>
        <Link href="/login" className="inline-block mt-4">
          <Button variant="primary">Sign In</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-1.5 bg-indigo-50 text-indigo-700 text-xs font-semibold px-3 py-1 rounded-full mb-2">
            <Calendar className="w-3.5 h-3.5" />
            <span>Viewing Visits & Tours</span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Viewing Appointments</h1>
          <p className="text-slate-500 text-sm mt-1">
            Track and manage scheduled physical walkthroughs and video call tours with verified landlords.
          </p>
        </div>

        <Link href="/properties">
          <Button variant="outline" size="sm" className="gap-2">
            <Building className="w-4 h-4" />
            <span>Browse Accommodations</span>
          </Button>
        </Link>
      </div>

      {actionNotice && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center space-x-2 text-xs text-emerald-800">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-slate-200 space-x-8 text-sm">
        <button
          onClick={() => setActiveTab("upcoming")}
          className={`pb-3 font-semibold transition-colors flex items-center space-x-2 border-b-2 ${
            activeTab === "upcoming"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <span>Upcoming Visits</span>
          <span className="text-xs bg-slate-100 px-2 py-0.5 rounded-full text-slate-600">
            {upcomingList.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("requests")}
          className={`pb-3 font-semibold transition-colors flex items-center space-x-2 border-b-2 ${
            activeTab === "requests"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <span>Host Requests</span>
          <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-bold">
            {requestsList.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("past")}
          className={`pb-3 font-semibold transition-colors flex items-center space-x-2 border-b-2 ${
            activeTab === "past"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <span>Past / Cancelled</span>
          <span className="text-xs bg-slate-100 px-2 py-0.5 rounded-full text-slate-600">
            {pastList.length}
          </span>
        </button>
      </div>

      {/* Appointments List */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 bg-slate-100 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : appointmentsQuery.error ? (
        <ErrorState
          title="Couldn't load your appointments"
          message={appointmentsQuery.error.message}
          onRetry={appointmentsQuery.refetch}
        />
      ) : currentDisplayList.length === 0 ? (
        <Card className="p-12 text-center border-slate-200/80">
          <Calendar className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-800">
            {activeTab === "upcoming"
              ? "No upcoming appointments scheduled"
              : activeTab === "requests"
              ? "No viewing requests pending your approval"
              : "No past appointment history"}
          </h3>
          <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
            Find an accommodation listing and schedule a physical visit or virtual call tour to inspect the premises.
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {currentDisplayList.map((appt) => {
            const isHost = appt.host_id === user?.id;
            return (
              <Card
                key={appt.id}
                className="p-5 border-slate-200/80 flex flex-col md:flex-row md:items-center md:justify-between gap-4 hover:shadow-xs transition-shadow"
              >
                <div className="space-y-2 flex-1">
                  <div className="flex items-center space-x-2">
                    <Badge
                      variant={
                        appt.status === "confirmed"
                          ? "success"
                          : appt.status === "rejected" || appt.status === "cancelled"
                          ? "danger"
                          : "warning"
                      }
                      size="sm"
                    >
                      {appt.status.toUpperCase()}
                    </Badge>

                    <div className="flex items-center space-x-1 text-xs text-slate-500">
                      {appt.appointment_type === "video_call" ? (
                        <>
                          <Video className="w-3.5 h-3.5 text-indigo-600" />
                          <span>Video Call Tour</span>
                        </>
                      ) : (
                        <>
                          <MapPin className="w-3.5 h-3.5 text-indigo-600" />
                          <span>In-Person Walkthrough</span>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center space-x-3 text-slate-800 text-sm font-bold">
                    <Clock className="w-4 h-4 text-indigo-600 flex-shrink-0" />
                    <span>{formatDateTimeIST(appt.scheduled_at)} (IST)</span>
                  </div>

                  {appt.notes && (
                    <p className="text-xs text-slate-500 italic bg-slate-50 p-2 rounded-lg">
                      &ldquo;{appt.notes}&rdquo;
                    </p>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center space-x-2">
                  {isHost && appt.status === "requested" && (
                    <>
                      <Button
                        size="sm"
                        variant="primary"
                        className="gap-1 bg-emerald-600 hover:bg-emerald-700"
                        onClick={() => handleUpdateStatus(appt.id, "confirmed")}
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span>Confirm Visit</span>
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="gap-1 text-rose-600 border-rose-200 hover:bg-rose-50"
                        onClick={() => handleUpdateStatus(appt.id, "rejected")}
                      >
                        <X className="w-3.5 h-3.5" />
                        <span>Reject</span>
                      </Button>
                    </>
                  )}

                  {!isHost && appt.status !== "cancelled" && appt.status !== "rejected" && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-rose-600 border-rose-200 hover:bg-rose-50 text-xs"
                      onClick={() => handleUpdateStatus(appt.id, "cancelled")}
                    >
                      Cancel Visit
                    </Button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
