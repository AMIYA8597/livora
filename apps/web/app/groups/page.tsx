"use client";

import React, { useState, useEffect } from "react";
import { GroupDTO } from "@flatmate/contracts";
import { apiClient } from "@/lib/api-client";
import { formatCurrency, formatDate } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";
import { Card, Button, Modal, Input, Badge } from "@flatmate/ui";
import { Users, Plus, MapPin, DollarSign, Calendar, Heart } from "lucide-react";

export default function GroupsPage() {
  const { isAuthenticated } = useAuth();
  const [groups, setGroups] = useState<GroupDTO[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Create Group Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [city, setCity] = useState("San Francisco");
  const [budget, setBudget] = useState("4200");
  const [moveIn, setMoveIn] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchGroups = async () => {
    try {
      setIsLoading(true);
      const data = await apiClient<GroupDTO[]>("/groups");
      setGroups(data);
    } catch (err) {
      console.error("Failed to load groups:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchGroups();
  }, []);

  const handleCreateGroup = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsSubmitting(true);
      await apiClient("/groups", {
        method: "POST",
        body: JSON.stringify({
          name,
          description,
          target_city: city,
          target_budget_total: parseInt(budget, 10),
          target_move_in: moveIn || undefined,
        }),
      });
      setIsModalOpen(false);
      fetchGroups();
    } catch (err: any) {
      alert(err.message || "Failed to create group");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleJoinGroup = async (groupId: string) => {
    try {
      await apiClient(`/groups/${groupId}/members`, { method: "POST" });
      alert("You have joined this hunting syndicate!");
      fetchGroups();
    } catch (err: any) {
      alert(err.message || "Failed to join group");
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-1.5 bg-purple-50 text-purple-700 text-xs font-semibold px-3 py-1 rounded-full mb-2">
            <Users className="w-3.5 h-3.5" />
            <span>Team-Up to Rent</span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Flatmate Hunting Groups</h1>
          <p className="text-slate-500 text-sm mt-1">
            Form syndicates with compatible seekers to search and apply for entire houses and apartments together.
          </p>
        </div>

        {isAuthenticated && (
          <Button variant="primary" className="gap-2" onClick={() => setIsModalOpen(true)}>
            <Plus className="w-4 h-4" />
            <span>Create a Group</span>
          </Button>
        )}
      </div>

      {/* Groups Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-pulse">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className="bg-slate-200 h-56 rounded-2xl" />
          ))}
        </div>
      ) : groups.length === 0 ? (
        <Card className="p-12 text-center max-w-lg mx-auto">
          <Users className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-800">No active groups in this area</h3>
          <p className="text-xs text-slate-500 mt-1">Be the first to start a flatmate syndicate!</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {groups.map((group) => (
            <Card key={group.id} className="p-6 border-slate-200/80 hover:shadow-md transition-shadow flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-bold text-slate-900 text-lg">{group.name}</h3>
                    <div className="flex items-center text-xs text-slate-500 space-x-2 mt-1">
                      <span className="flex items-center space-x-1">
                        <MapPin className="w-3.5 h-3.5 text-slate-400" />
                        <span>{group.target_city}</span>
                      </span>
                      <span>•</span>
                      <span className="flex items-center space-x-1">
                        <Calendar className="w-3.5 h-3.5 text-slate-400" />
                        <span>Move-in: {formatDate(group.target_move_in)}</span>
                      </span>
                    </div>
                  </div>
                  <Badge variant="info" size="sm">
                    {group.members.length} Members
                  </Badge>
                </div>

                <p className="text-xs text-slate-600 mt-3 line-clamp-2 leading-relaxed">
                  {group.description || "Looking for compatible flatmates to rent a multi-bedroom place together."}
                </p>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-between">
                <div>
                  <span className="text-[11px] text-slate-400 uppercase font-semibold block">Combined Target Budget</span>
                  <span className="text-base font-bold text-slate-900">{formatCurrency(group.target_budget_total)}/mo</span>
                </div>
                <Button size="sm" variant="secondary" onClick={() => handleJoinGroup(group.id)}>
                  Join Syndicate
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create Group Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Start a Flatmate Syndicate"
        description="Create a group to invite seekers and organize joint applications."
      >
        <form onSubmit={handleCreateGroup} className="space-y-4 mt-2">
          <Input
            label="Group Name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Mission / Hayes Valley Co-Living Trio"
          />

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Description & Goals</label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What kind of place are you aiming for? What are your living expectations?"
              className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Target City"
              required
              value={city}
              onChange={(e) => setCity(e.target.value)}
            />
            <Input
              label="Combined Budget ($)"
              type="number"
              required
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
            />
          </div>

          <Input
            label="Target Move-In Date"
            type="date"
            value={moveIn}
            onChange={(e) => setMoveIn(e.target.value)}
          />

          <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isSubmitting}>
            Launch Group
          </Button>
        </form>
      </Modal>
    </div>
  );
}
