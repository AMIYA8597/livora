"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { PropertyDTO } from "@flatmate/contracts";
import { apiClient } from "@/lib/api-client";
import { formatCurrency, formatDate } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";
import { Button, Card, Badge, Modal, Input } from "@flatmate/ui";
import { MapPin, Bed, Bath, Sparkles, CheckCircle2, ShieldCheck, Calendar, ArrowLeft } from "lucide-react";

export default function PropertyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const propertyId = params.id as string;

  const [property, setProperty] = useState<PropertyDTO | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Application Modal state
  const [isApplyModalOpen, setIsApplyModalOpen] = useState(false);
  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(null);
  const [introduction, setIntroduction] = useState("");
  const [proposedRent, setProposedRent] = useState("");
  const [moveInTarget, setMoveInTarget] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [applySuccess, setApplySuccess] = useState(false);

  useEffect(() => {
    async function loadProperty() {
      try {
        setIsLoading(true);
        const data = await apiClient<PropertyDTO>(`/properties/${propertyId}`);
        setProperty(data);
        setProposedRent(String(data.monthly_rent));
      } catch (err) {
        console.error("Failed to load property:", err);
      } finally {
        setIsLoading(false);
      }
    }
    if (propertyId) loadProperty();
  }, [propertyId]);

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

  if (isLoading) {
    return <div className="max-w-7xl mx-auto px-4 py-20 text-center text-slate-500">Loading property...</div>;
  }

  if (!property) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-20 text-center">
        <h2 className="text-xl font-bold text-slate-900">Property not found</h2>
        <Button variant="outline" className="mt-4" onClick={() => router.push("/properties")}>
          Back to Listings
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <button
        onClick={() => router.back()}
        className="inline-flex items-center text-xs font-semibold text-slate-600 hover:text-indigo-600 transition-colors"
      >
        <ArrowLeft className="w-4 h-4 mr-1" />
        Back to Listings
      </button>

      {/* Media Carousel */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 rounded-3xl overflow-hidden max-h-[460px]">
        <div className="md:col-span-2 h-[300px] md:h-[460px] bg-slate-200">
          <img
            src={property.images[0] || "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800"}
            alt={property.title}
            className="w-full h-full object-cover"
          />
        </div>
        <div className="hidden md:flex flex-col gap-4 h-[460px]">
          <div className="flex-1 bg-slate-200 overflow-hidden">
            <img
              src={property.images[1] || "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800"}
              alt="Interior"
              className="w-full h-full object-cover"
            />
          </div>
          <div className="flex-1 bg-slate-200 overflow-hidden">
            <img
              src={property.images[2] || "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800"}
              alt="Room"
              className="w-full h-full object-cover"
            />
          </div>
        </div>
      </div>

      {/* Main Details and Application Card */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Details */}
        <div className="lg:col-span-2 space-y-8">
          <div>
            <div className="flex items-center space-x-1.5 text-xs text-slate-500 mb-2">
              <MapPin className="w-4 h-4 text-slate-400" />
              <span>{property.address}, {property.city}, {property.postal_code}</span>
            </div>
            <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">{property.title}</h1>

            <div className="flex flex-wrap gap-4 mt-4 pt-4 border-t border-slate-100 text-sm text-slate-700">
              <div className="flex items-center space-x-1.5">
                <Bed className="w-4 h-4 text-indigo-600" />
                <span className="font-semibold">{property.total_bedrooms} Bedrooms</span>
              </div>
              <div className="flex items-center space-x-1.5">
                <Bath className="w-4 h-4 text-indigo-600" />
                <span className="font-semibold">{property.total_bathrooms} Bathrooms</span>
              </div>
              <div className="flex items-center space-x-1.5">
                <Calendar className="w-4 h-4 text-indigo-600" />
                <span>Available {formatDate(property.available_from)}</span>
              </div>
            </div>
          </div>

          {/* Description */}
          <div>
            <h3 className="text-lg font-bold text-slate-900 mb-2">About the Property</h3>
            <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-line">
              {property.description}
            </p>
          </div>

          {/* Available Rooms */}
          {property.rooms && property.rooms.length > 0 && (
            <div>
              <h3 className="text-lg font-bold text-slate-900 mb-3">Individual Rooms Available</h3>
              <div className="space-y-3">
                {property.rooms.map((room) => (
                  <div
                    key={room.id}
                    className="p-4 bg-white rounded-2xl border border-slate-200/80 flex items-center justify-between shadow-2xs"
                  >
                    <div>
                      <h4 className="font-semibold text-slate-900 text-sm">{room.room_name}</h4>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {room.private_bath ? "Private En-Suite Bath" : "Shared Bath"} • Available {formatDate(room.available_from)}
                      </p>
                    </div>
                    <div className="flex items-center space-x-3">
                      <span className="font-bold text-slate-900 text-sm">
                        {formatCurrency(room.room_rent)}/mo
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

          {/* Amenities */}
          <div>
            <h3 className="text-lg font-bold text-slate-900 mb-3">Included Amenities</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              {property.amenities.map((amenity) => (
                <div
                  key={amenity}
                  className="flex items-center space-x-2 text-xs font-medium text-slate-700 bg-slate-100/80 px-3 py-2 rounded-xl"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span className="capitalize">{amenity.replace(/_/g, " ")}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Pricing & Apply Sticky Box */}
        <div>
          <Card className="p-6 sticky top-24 border-slate-200/80 shadow-md space-y-6">
            <div>
              <span className="text-xs text-slate-500 font-medium">Entire Property Rent</span>
              <div className="text-3xl font-extrabold text-slate-900">
                {formatCurrency(property.monthly_rent)}
                <span className="text-sm font-normal text-slate-500"> /month</span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Deposit: {formatCurrency(property.deposit)} • {property.bills_included ? "Bills included" : "Utilities separate"}
              </p>
            </div>

            <Button
              variant="primary"
              size="lg"
              className="w-full shadow-md"
              onClick={() => {
                setSelectedRoomId(null);
                setProposedRent(String(property.monthly_rent));
                setIsApplyModalOpen(true);
              }}
            >
              Apply for Entire Property
            </Button>

            <div className="pt-4 border-t border-slate-100 space-y-2 text-xs text-slate-500">
              <div className="flex items-center space-x-2 text-emerald-600 font-medium">
                <ShieldCheck className="w-4 h-4" />
                <span>Verified Landlord</span>
              </div>
              <p>No deposit required until formal lease review.</p>
            </div>
          </Card>
        </div>
      </div>

      {/* Tenancy Application Modal */}
      <Modal
        isOpen={isApplyModalOpen}
        onClose={() => setIsApplyModalOpen(false)}
        title="Submit Tenancy Application"
        description="Share your introduction with the property owner."
      >
        {applySuccess ? (
          <div className="text-center py-6">
            <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-2" />
            <h4 className="font-bold text-slate-900 text-base">Application Submitted!</h4>
            <p className="text-xs text-slate-500 mt-1">The owner has been notified and will review your profile.</p>
          </div>
        ) : (
          <form onSubmit={handleApplySubmit} className="space-y-4 mt-2">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Introduction to the Host
              </label>
              <textarea
                required
                rows={4}
                value={introduction}
                onChange={(e) => setIntroduction(e.target.value)}
                placeholder="Hi! Tell them a bit about yourself, your occupation, and why this flat is a great fit..."
                className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <Input
              label="Proposed Monthly Rent ($)"
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
              Send Application
            </Button>
          </form>
        )}
      </Modal>
    </div>
  );
}
