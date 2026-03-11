import { cn } from "@/lib/utils";

const statusConfig = {
  uploading: { label: "Uploading", color: "bg-yellow-100 text-yellow-800" },
  processing: { label: "Processing", color: "bg-blue-100 text-blue-800 animate-pulse" },
  ready: { label: "Ready", color: "bg-green-100 text-green-800" },
  error: { label: "Error", color: "bg-red-100 text-red-800" },
};

export default function StatusBadge({
  status,
}: {
  status: keyof typeof statusConfig;
}) {
  const config = statusConfig[status] || statusConfig.error;

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        config.color,
      )}
    >
      {config.label}
    </span>
  );
}
