"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Menu } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/",          icon: "🎬", label: "Live Demo",     accent: true },
  { href: "/dashboard", icon: "📊", label: "Dashboard" },
  { href: "/chat",      icon: "💬", label: "Chat History" },
  { href: "/users",     icon: "👤", label: "Users" },
  { href: "/consent",   icon: "✅", label: "Consent" },
  { href: "/audit",     icon: "📋", label: "Audit Trail" },
  { href: "/infer",     icon: "⚡", label: "Inference" },
  { href: "/webhook",   icon: "🔗", label: "Webhook" },
  { href: "/policy",    icon: "🔍", label: "Policy Scanner" },
];

function NavContent({ onClose }: { onClose?: () => void }) {
  const pathname = usePathname();

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--cf-surface)" }}>
      {/* Logo */}
      <div className="px-5 py-5 border-b" style={{ borderColor: "var(--cf-border)" }}>
        <div className="flex items-center gap-2">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-black"
            style={{ background: "linear-gradient(135deg, #7c6dfa, #3ecfb2)" }}
          >
            CF
          </div>
          <span
            className="text-base font-bold"
            style={{
              background: "linear-gradient(135deg, #7c6dfa, #3ecfb2)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            ConsentFlow
          </span>
        </div>
      </div>

      {/* Nav items */}
      <nav className="flex-1 p-3 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onClose}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 group",
                isActive
                  ? "border-l-2 border-cf-purple"
                  : "border-l-2 border-transparent hover:bg-white/5"
              )}
              style={{
                backgroundColor: isActive ? "rgba(124,109,250,0.1)" : undefined,
                color: isActive
                  ? "var(--cf-purple)"
                  : item.accent
                  ? "var(--cf-teal)"
                  : "var(--cf-text)",
              }}
            >
              <span className="text-base">{item.icon}</span>
              <span className={cn("font-medium", isActive && "font-semibold")}>
                {item.label}
              </span>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t" style={{ borderColor: "var(--cf-border)" }}>
        <p className="text-xs" style={{ color: "var(--cf-muted)" }}>
          Powered by
        </p>
        <p className="text-xs font-medium mt-0.5" style={{ color: "var(--cf-muted)" }}>
          Gemini 2.0 Flash + Presidio
        </p>
      </div>
    </div>
  );
}

export function Sidebar() {
  return (
    <aside
      className="hidden md:flex flex-col fixed left-0 top-0 bottom-0 z-40"
      style={{ width: "220px", borderRight: "1px solid var(--cf-border)" }}
    >
      <NavContent />
    </aside>
  );
}

export function MobileSidebar() {
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button
          className="md:hidden fixed top-3 left-3 z-50 p-2 rounded-lg"
          style={{ background: "var(--cf-surface2)", border: "1px solid var(--cf-border)" }}
        >
          <Menu size={18} style={{ color: "var(--cf-text)" }} />
        </button>
      </SheetTrigger>
      <SheetContent side="left" className="p-0 w-[220px]" style={{ background: "var(--cf-surface)" }}>
        <NavContent onClose={() => setOpen(false)} />
      </SheetContent>
    </Sheet>
  );
}
