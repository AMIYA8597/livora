"use client";

import React, { useRef, useState } from "react";
import type { ProfileDTO, UserDTO, UserTrustStatusDTO } from "@flatmate/contracts";
import { Avatar, Badge } from "@flatmate/ui";
import { CheckCircle2, ShieldCheck, Upload } from "lucide-react";
import { apiClient } from "@/lib/api-client";

interface ProfileHeaderProps {
  user: UserDTO | null;
  profile: ProfileDTO | null;
  trust: UserTrustStatusDTO | null;
  onAvatarChanged: (profile: ProfileDTO) => void;
  onNotice: (message: string, tone?: "success" | "error") => void;
}

export function ProfileHeader({ user, profile, trust, onAvatarChanged, onNotice }: ProfileHeaderProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const name = profile?.display_name || user?.full_name || "User";

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("bucket", "avatars");
      const uploaded = await apiClient.upload<{ file_url: string }>("/storage/upload", formData);
      if (uploaded?.file_url) {
        const updated = await apiClient<ProfileDTO>("/profiles/me", {
          method: "PUT",
          body: JSON.stringify({ avatar_url: uploaded.file_url }),
        });
        onAvatarChanged(updated);
        onNotice("Profile photo updated.");
      }
    } catch (err) {
      onNotice(err instanceof Error ? err.message : "Photo upload failed", "error");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-xs flex flex-col md:flex-row items-center gap-6">
      <div className="relative">
        <Avatar
          src={profile?.avatar_url || undefined}
          alt={name}
          size="xl"
          isVerified={trust?.is_fully_verified ?? user?.is_verified}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          aria-label="Upload profile photo"
          className="absolute -bottom-1 -right-1 w-11 h-11 flex items-center justify-center bg-forest text-white rounded-full shadow-md hover:bg-forest-light disabled:opacity-60 transition-colors"
        >
          <Upload className="w-4 h-4" />
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          onChange={handleAvatarUpload}
        />
      </div>

      <div className="flex-1 text-center md:text-left min-w-0">
        <div className="flex flex-wrap items-center justify-center md:justify-start gap-2 mb-1">
          <h1 className="text-2xl font-bold text-charcoal break-words">{name}</h1>
          {trust?.is_fully_verified && (
            <Badge variant="forest">
              <ShieldCheck className="w-3 h-3 mr-1 inline" /> Verified resident
            </Badge>
          )}
          <Badge variant="default" className="uppercase text-[10px] tracking-wider">
            {user?.role || "seeker"}
          </Badge>
        </div>
        <p className="text-xs text-charcoal-muted mb-2 break-all">{user?.email}</p>
        <p className="text-sm text-charcoal max-w-xl">
          {profile?.bio || "Tell roommates about yourself, your hobbies, and what you look for in a flatmate."}
        </p>
      </div>

      <div className="text-center md:text-right">
        <div className="text-xs text-charcoal-muted">Trust score</div>
        <div className="text-2xl font-black text-forest">
          {trust?.total_trust_score ?? "—"}
          <span className="text-xs font-normal text-charcoal-muted">/100</span>
        </div>
        <div className="text-[11px] text-emerald-600 flex items-center justify-center md:justify-end gap-1 mt-1 font-medium">
          <CheckCircle2 className="w-3 h-3" /> Account active
        </div>
      </div>
    </div>
  );
}
