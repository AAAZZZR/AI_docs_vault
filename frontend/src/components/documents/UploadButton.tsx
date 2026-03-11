"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Loader2, Upload, CheckCircle, AlertCircle } from "lucide-react";
import { uploadPDF, type UploadProgress } from "@/lib/upload";
import { cn } from "@/lib/utils";

interface UploadButtonProps {
  onUploadComplete: () => void;
}

export default function UploadButton({ onUploadComplete }: UploadButtonProps) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<UploadProgress | null>(null);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;

      setUploading(true);
      setProgress(null);

      try {
        await uploadPDF(file, (p) => setProgress(p));
        setProgress({
          phase: "ready",
          progress: 100,
          detail: "Document ready!",
        });
        onUploadComplete();
        // Clear after showing success briefly
        setTimeout(() => {
          setUploading(false);
          setProgress(null);
        }, 2000);
      } catch (err) {
        console.error("Upload failed:", err);
        setProgress({
          phase: "error",
          progress: 0,
          detail: err instanceof Error ? err.message : "Upload failed",
        });
        setTimeout(() => {
          setUploading(false);
          setProgress(null);
        }, 4000);
      }
    },
    [onUploadComplete],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    maxFiles: 1,
    maxSize: 100 * 1024 * 1024,
    disabled: uploading,
  });

  const getIcon = () => {
    if (!uploading || !progress) return <Upload className="h-4 w-4 text-gray-400" />;
    switch (progress.phase) {
      case "error":
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case "ready":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      default:
        return <Loader2 className="h-4 w-4 animate-spin text-indigo-600" />;
    }
  };

  const getTextColor = () => {
    if (!progress) return "text-gray-600";
    switch (progress.phase) {
      case "error":
        return "text-red-600";
      case "ready":
        return "text-green-600";
      default:
        return "text-indigo-600";
    }
  };

  return (
    <div>
      <div
        {...getRootProps()}
        className={cn(
          "cursor-pointer rounded-lg border-2 border-dashed px-4 py-3 text-center transition-colors",
          isDragActive
            ? "border-indigo-400 bg-indigo-50"
            : "border-gray-300 hover:border-indigo-300 hover:bg-indigo-50/50",
          uploading && "cursor-not-allowed opacity-60",
        )}
      >
        <input {...getInputProps()} />
        <div className="flex items-center justify-center gap-2">
          {getIcon()}
          <span className={cn("text-sm", getTextColor())}>
            {uploading && progress
              ? progress.detail
              : isDragActive
                ? "Drop PDF here..."
                : "Upload PDF or drag & drop"}
          </span>
        </div>
        {/* Progress bar */}
        {uploading && progress && progress.phase !== "error" && (
          <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-gray-200">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-500",
                progress.phase === "ready" ? "bg-green-500" : "bg-indigo-500",
              )}
              style={{ width: `${progress.progress}%` }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
