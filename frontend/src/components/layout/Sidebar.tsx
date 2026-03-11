"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileText, MessageSquare, Vault } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", label: "Knowledge Base", icon: FileText },
  { href: "/chat", label: "Chat", icon: MessageSquare },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-64 flex-col border-r border-gray-200 bg-white">
      {/* Logo */}
      <div className="flex items-center gap-2 border-b border-gray-200 px-6 py-4">
        <Vault className="h-6 w-6 text-indigo-600" />
        <span className="text-lg font-semibold text-gray-900">DocVault</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-indigo-50 text-indigo-700"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-gray-200 px-4 py-3 text-xs text-gray-400">
        Local Knowledge Base
      </div>
    </aside>
  );
}
