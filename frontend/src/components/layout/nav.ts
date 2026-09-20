import { Building2, LayoutDashboard, Microscope, Radar, Settings, Target } from "lucide-react";
import type * as React from "react";

export interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/targets", label: "Targets", icon: Target },
  { href: "/companies", label: "Companies", icon: Building2 },
  { href: "/runs", label: "Discovery Runs", icon: Radar },
  { href: "/research", label: "Research", icon: Microscope },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}
