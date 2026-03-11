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
          phase: "processing",
          progress: 70,
          detail: "Document is being analyzed...",
        });
        // Refresh the document list after a short delay
        setTimeout(() => {
          onUploadComplete();
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
        }, 3000);
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
        {uploading && progress ? (
          <div className="flex items-center justify-center gap-2">
            {progress.phase === "error" ? (
              <AlertCircle className="h-4 w-4 text-red-500" />
            ) : (
              <Loader2 className="h-4 w-4 animate-spin text-indigo-600" />
            )}
            <span
              className={cn(
                "text-sm",
                progress.phase === "error"
                  ? "text-red-600"
                  : "text-indigo-600",
              )}
            >
              {progress.detail}
            </span>
          </div>
        ) : (
          <div className="flex items-center justify-center gap-2">
            <Upload className="h-4 w-4 text-gray-400" />
            <span className="text-sm text-gray-600">
              {isDragActive
                ? "Drop PDF here..."
                : "Upload PDF or drag & drop"}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
