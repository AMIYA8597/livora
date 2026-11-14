"use client";

import React, { useState, useRef } from "react";
import { Upload, X, CheckCircle2, AlertCircle, FileText, Lock, Loader2 } from "lucide-react";
import { Button } from "@flatmate/ui";
import { apiClient } from "@/lib/api-client";

export interface FileUploadProps {
  bucket: "properties" | "avatars" | "verification";
  purpose?: string;
  resourceId?: string;
  onUploadSuccess: (res: {
    url: string;
    path: string;
    bucket: string;
    object_id?: string;
    is_private?: boolean;
  }) => void;
  onUploadError?: (err: string) => void;
  label?: string;
  helperText?: string;
  currentPreviewUrl?: string | null;
  onRemove?: () => void;
  className?: string;
}

const MAX_SIZES: Record<string, number> = {
  properties: 10 * 1024 * 1024,   // 10 MB
  avatars: 5 * 1024 * 1024,       // 5 MB
  verification: 15 * 1024 * 1024, // 15 MB
};

const ALLOWED_MIMES: Record<string, string[]> = {
  properties: ["image/jpeg", "image/png", "image/webp"],
  avatars: ["image/jpeg", "image/png", "image/webp"],
  verification: ["application/pdf", "image/jpeg", "image/png"],
};

export const FileUpload: React.FC<FileUploadProps> = ({
  bucket,
  purpose,
  resourceId,
  onUploadSuccess,
  onUploadError,
  label,
  helperText,
  currentPreviewUrl,
  onRemove,
  className = "",
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [preview, setPreview] = useState<string | null>(currentPreviewUrl || null);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const maxSize = MAX_SIZES[bucket] || 10 * 1024 * 1024;
  const allowedMimes = ALLOWED_MIMES[bucket] || ["image/jpeg", "image/png"];
  const isPrivate = bucket === "verification";

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setError(null);
    setSuccess(false);

    // 1. Validation
    if (!allowedMimes.includes(file.type)) {
      const msg = `Unsupported file type. Allowed: ${allowedMimes.map((m) => m.split("/")[1].toUpperCase()).join(", ")}`;
      setError(msg);
      if (onUploadError) onUploadError(msg);
      return;
    }

    if (file.size > maxSize) {
      const msg = `File exceeds size limit of ${Math.round(maxSize / (1024 * 1024))}MB`;
      setError(msg);
      if (onUploadError) onUploadError(msg);
      return;
    }

    setSelectedFileName(file.name);

    // Preview
    if (file.type.startsWith("image/")) {
      const localUrl = URL.createObjectURL(file);
      setPreview(localUrl);
    } else {
      setPreview(null);
    }

    // 2. Upload
    setIsUploading(true);
    setProgress(20);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("bucket", bucket);
      if (purpose) formData.append("purpose", purpose);
      if (resourceId) formData.append("resource_id", resourceId);

      setProgress(60);

      const res = await apiClient<{
        url: string;
        path: string;
        bucket: string;
        object_id?: string;
        is_private?: boolean;
      }>("/storage/upload", {
        method: "POST",
        body: formData,
      });

      setProgress(100);
      setSuccess(true);
      onUploadSuccess(res);
    } catch (err: any) {
      const msg = err.message || "Failed to upload file. Please try again.";
      setError(msg);
      if (onUploadError) onUploadError(msg);
    } finally {
      setIsUploading(false);
    }
  };

  const handleClear = () => {
    setPreview(null);
    setSelectedFileName(null);
    setError(null);
    setSuccess(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (onRemove) onRemove();
  };

  return (
    <div className={`space-y-2 ${className}`}>
      {label && (
        <label className="block text-xs font-semibold text-slate-700">
          {label}
          {isPrivate && (
            <span className="ml-2 inline-flex items-center text-[11px] text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full font-medium">
              <Lock className="w-3 h-3 mr-1" />
              Private & Encrypted
            </span>
          )}
        </label>
      )}

      {error && (
        <div className="flex items-center space-x-1.5 p-2 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs">
          <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Dropzone / Card */}
      <div className="relative border-2 border-dashed border-slate-300 hover:border-indigo-400 rounded-2xl p-4 transition-colors bg-slate-50/50">
        <input
          ref={fileInputRef}
          type="file"
          accept={allowedMimes.join(",")}
          onChange={handleFileChange}
          disabled={isUploading}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
        />

        {preview ? (
          <div className="flex items-center space-x-3">
            <img
              src={preview}
              alt="Uploaded Preview"
              className="w-16 h-16 rounded-xl object-cover border border-slate-200"
            />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-slate-800 truncate">
                {selectedFileName || "Image selected"}
              </p>
              {success && (
                <span className="inline-flex items-center text-[11px] text-emerald-600 font-medium mt-0.5">
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Uploaded securely
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={handleClear}
              className="p-1 text-slate-400 hover:text-rose-600 rounded-lg"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ) : selectedFileName && isPrivate ? (
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-xl flex items-center justify-center">
              <FileText className="w-6 h-6" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-slate-800 truncate">{selectedFileName}</p>
              {success && (
                <span className="inline-flex items-center text-[11px] text-emerald-600 font-medium">
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Document encrypted & uploaded
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={handleClear}
              className="p-1 text-slate-400 hover:text-rose-600 rounded-lg"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="text-center py-4">
            <div className="w-10 h-10 bg-indigo-50 text-indigo-600 rounded-xl flex items-center justify-center mx-auto mb-2">
              <Upload className="w-5 h-5" />
            </div>
            <p className="text-xs font-medium text-slate-700">
              Click or drag file to upload
            </p>
            <p className="text-[11px] text-slate-400 mt-0.5">
              {helperText || `Max size: ${Math.round(maxSize / (1024 * 1024))}MB`}
            </p>
          </div>
        )}

        {isUploading && (
          <div className="mt-3 space-y-1">
            <div className="flex justify-between text-[11px] text-slate-500 font-medium">
              <span>Uploading to secure storage...</span>
              <span>{progress}%</span>
            </div>
            <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-indigo-600 h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
