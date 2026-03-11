import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface TagChipProps {
  name: string;
  color?: string | null;
  selected?: boolean;
  count?: number;
  removable?: boolean;
  onClick?: () => void;
  onRemove?: () => void;
}

export default function TagChip({
  name,
  color,
  selected = false,
  count,
  removable = false,
  onClick,
  onRemove,
}: TagChipProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors",
        selected
          ? "bg-indigo-100 text-indigo-800 ring-1 ring-indigo-300"
          : "bg-gray-100 text-gray-700 hover:bg-gray-200",
      )}
      style={color ? { backgroundColor: `${color}20`, color } : undefined}
    >
      {name}
      {count !== undefined && (
        <span className="text-[10px] opacity-60">{count}</span>
      )}
      {removable && onRemove && (
        <X
          className="ml-0.5 h-3 w-3 cursor-pointer opacity-50 hover:opacity-100"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
        />
      )}
    </button>
  );
}
