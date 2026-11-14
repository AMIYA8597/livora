"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api-client";
import { Avatar, Button, Badge } from "@flatmate/ui";
import {
  Compass,
  Users,
  Sparkles,
  Users2,
  MessageSquare,
  LayoutDashboard,
  Bell,
  Check,
  ChevronDown,
  Building,
  KeyRound,
  ShieldAlert,
  UserCircle,
  Settings,
  LogOut,
  Menu,
  X,
  Search,
} from "lucide-react";

interface NotificationItem {
  id: string;
  title: string;
  message: string;
  type: string;
  is_read: boolean;
  created_at: string;
}

export const Navbar: React.FC = () => {
  const pathname = usePathname();
  const router = useRouter();
  const { user, roles, isAuthenticated, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [profileDropdownOpen, setProfileDropdownOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  const notifRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotificationsOpen(false);
      }
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, []);

  // Fetch notifications for authenticated users
  useEffect(() => {
    if (!isAuthenticated) return;

    let isMounted = true;
    const fetchNotifications = async () => {
      try {
        const res = await apiClient<{ items: NotificationItem[]; total: number } | NotificationItem[]>("/notifications/");
        const items = Array.isArray(res) ? res : res.items || [];
        if (isMounted) {
          setNotifications(items);
          setUnreadCount(items.filter((n) => !n.is_read).length);
        }
      } catch {
        // Fallback silently if offline or unread endpoint empty
      }
    };

    fetchNotifications();
    const interval = setInterval(fetchNotifications, 45000); // 45s poll
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [isAuthenticated]);

  const markNotificationAsRead = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await apiClient(`/notifications/${id}/read`, { method: "PATCH" });
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch {
      // Ignored
    }
  };

  const navLinks = [
    { href: "/properties", label: "Discover", icon: Compass },
    { href: "/flatmates", label: "Flatmates", icon: Users },
    { href: "/matches", label: "Matches", icon: Sparkles },
    { href: "/groups", label: "Groups", icon: Users2 },
    { href: "/messages", label: "Messages", icon: MessageSquare, authOnly: true },
    { href: "/dashboard", label: "My Space", icon: LayoutDashboard, authOnly: true },
  ];

  const isOwner = roles.includes("owner") || user?.role === "owner";
  const isTenant = roles.includes("tenant") || user?.role === "tenant";
  const isPG = roles.includes("pg_operator") || user?.role === "pg_operator";
  const isAdmin = roles.includes("admin") || roles.includes("super_admin") || user?.role === "admin";

  return (
    <nav className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-warm-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Brand Logo */}
          <div className="flex items-center space-x-3">
            <Link href="/" className="flex items-center space-x-2.5 focus:outline-none">
              <div className="w-9 h-9 rounded-xl bg-forest flex items-center justify-center text-white shadow-sm shadow-forest/20">
                <Compass className="w-5 h-5 text-pale-green" />
              </div>
              <div className="flex flex-col">
                <span className="font-bold text-xl tracking-tight text-charcoal leading-none">
                  flatmate<span className="text-secondary-green">.</span>
                </span>
                <span className="text-[10px] text-charcoal-muted tracking-wide uppercase font-semibold mt-0.5 hidden sm:block">
                  Find your people
                </span>
              </div>
            </Link>
          </div>

          {/* Desktop Navigation Links */}
          <div className="hidden lg:flex items-center space-x-1">
            {navLinks.map((item) => {
              if (item.authOnly && !isAuthenticated) return null;
              const Icon = item.icon;
              const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={isActive ? "page" : undefined}
                  className={`flex items-center space-x-1.5 px-3 py-2 rounded-xl text-sm font-medium transition-all ${
                    isActive
                      ? "text-forest bg-pale-green/40 font-semibold"
                      : "text-charcoal-light hover:text-charcoal hover:bg-slate-100/70"
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? "text-forest" : "text-charcoal-muted"}`} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>

          {/* Right Action & Profile Area */}
          <div className="hidden sm:flex items-center space-x-3">
            {/* Quick Search trigger */}
            <Link
              href="/properties"
              className="p-2 text-charcoal-muted hover:text-charcoal hover:bg-slate-100 rounded-xl transition-colors"
              title="Search accommodation"
              aria-label="Search properties"
            >
              <Search className="w-4 h-4" />
            </Link>

            {isAuthenticated && user ? (
              <div className="flex items-center space-x-2">
                {/* Notifications Bell with Popover */}
                <div className="relative" ref={notifRef}>
                  <button
                    onClick={() => setNotificationsOpen(!notificationsOpen)}
                    aria-label="Notifications"
                    aria-expanded={notificationsOpen}
                    className="p-2 text-charcoal-light hover:text-forest hover:bg-slate-100 rounded-xl transition-colors relative"
                  >
                    <Bell className="w-5 h-5" />
                    {unreadCount > 0 && (
                      <span className="absolute top-1 right-1 min-w-[18px] h-[18px] bg-rose-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1">
                        {unreadCount > 9 ? "9+" : unreadCount}
                      </span>
                    )}
                  </button>

                  {/* Notification Dropdown */}
                  {notificationsOpen && (
                    <div className="absolute right-0 mt-2 w-80 bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-150">
                      <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
                        <span className="text-xs font-bold uppercase tracking-wider text-charcoal">
                          Notifications
                        </span>
                        {unreadCount > 0 && (
                          <span className="text-[11px] bg-forest text-white px-2 py-0.5 rounded-full font-semibold">
                            {unreadCount} new
                          </span>
                        )}
                      </div>
                      <div className="max-h-72 overflow-y-auto divide-y divide-slate-100">
                        {notifications.length === 0 ? (
                          <div className="p-6 text-center text-xs text-charcoal-muted">
                            No notifications right now.
                          </div>
                        ) : (
                          notifications.slice(0, 6).map((notif) => (
                            <div
                              key={notif.id}
                              className={`p-3.5 hover:bg-slate-50/80 transition-colors flex items-start justify-between space-x-2 ${
                                !notif.is_read ? "bg-pale-green/15" : ""
                              }`}
                            >
                              <div className="flex-1 text-xs">
                                <p className="font-semibold text-charcoal">{notif.title}</p>
                                <p className="text-slate-500 mt-0.5 line-clamp-2">{notif.message}</p>
                              </div>
                              {!notif.is_read && (
                                <button
                                  onClick={(e) => markNotificationAsRead(notif.id, e)}
                                  title="Mark as read"
                                  className="p-1 text-secondary-green hover:bg-pale-green/30 rounded-lg shrink-0"
                                >
                                  <Check className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </div>
                          ))
                        )}
                      </div>
                      <Link
                        href="/dashboard"
                        onClick={() => setNotificationsOpen(false)}
                        className="block py-2.5 text-center text-xs font-semibold text-secondary-green hover:bg-slate-50 border-t border-slate-100"
                      >
                        View all in My Space →
                      </Link>
                    </div>
                  )}
                </div>

                {/* Profile Menu Dropdown */}
                <div className="relative" ref={profileRef}>
                  <button
                    onClick={() => setProfileDropdownOpen(!profileDropdownOpen)}
                    aria-expanded={profileDropdownOpen}
                    aria-label="User menu"
                    className="flex items-center space-x-2 p-1.5 rounded-xl hover:bg-slate-100 transition-colors border border-transparent hover:border-slate-200"
                  >
                    <Avatar alt={user.full_name} size="sm" isVerified={user.is_verified} />
                    <span className="text-sm font-semibold text-charcoal hidden md:inline-block max-w-[100px] truncate">
                      {user.full_name.split(" ")[0]}
                    </span>
                    <ChevronDown className="w-3.5 h-3.5 text-charcoal-muted" />
                  </button>

                  {profileDropdownOpen && (
                    <div className="absolute right-0 mt-2 w-64 bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden z-50">
                      {/* User Header */}
                      <div className="px-4 py-3 bg-warm-50 border-b border-warm-200">
                        <p className="text-xs font-semibold text-charcoal truncate">{user.full_name}</p>
                        <p className="text-[11px] text-charcoal-muted truncate">{user.email}</p>
                        <div className="flex items-center space-x-1.5 mt-1.5">
                          <Badge variant="brand" size="sm">
                            {user.role}
                          </Badge>
                          {user.is_verified && (
                            <Badge variant="success" size="sm">
                              Verified
                            </Badge>
                          )}
                        </div>
                      </div>

                      {/* Menu Items */}
                      <div className="p-1 text-xs">
                        <Link
                          href="/profile"
                          onClick={() => setProfileDropdownOpen(false)}
                          className="flex items-center space-x-2.5 px-3 py-2 rounded-lg text-charcoal hover:bg-slate-100 transition-colors"
                        >
                          <UserCircle className="w-4 h-4 text-charcoal-muted" />
                          <span>Profile & Questionnaire</span>
                        </Link>

                        <Link
                          href="/dashboard"
                          onClick={() => setProfileDropdownOpen(false)}
                          className="flex items-center space-x-2.5 px-3 py-2 rounded-lg text-charcoal hover:bg-slate-100 transition-colors"
                        >
                          <LayoutDashboard className="w-4 h-4 text-charcoal-muted" />
                          <span>My Space & Applications</span>
                        </Link>

                        {/* Role-Aware Shortcuts */}
                        {isOwner && (
                          <Link
                            href="/owner"
                            onClick={() => setProfileDropdownOpen(false)}
                            className="flex items-center space-x-2.5 px-3 py-2 rounded-lg text-secondary-green hover:bg-pale-green/20 font-medium transition-colors"
                          >
                            <Building className="w-4 h-4" />
                            <span>Owner Dashboard</span>
                          </Link>
                        )}

                        {isTenant && (
                          <Link
                            href="/tenants"
                            onClick={() => setProfileDropdownOpen(false)}
                            className="flex items-center space-x-2.5 px-3 py-2 rounded-lg text-secondary-green hover:bg-pale-green/20 font-medium transition-colors"
                          >
                            <KeyRound className="w-4 h-4" />
                            <span>Tenant Vacancies</span>
                          </Link>
                        )}

                        {isPG && (
                          <Link
                            href="/pg"
                            onClick={() => setProfileDropdownOpen(false)}
                            className="flex items-center space-x-2.5 px-3 py-2 rounded-lg text-secondary-green hover:bg-pale-green/20 font-medium transition-colors"
                          >
                            <Building className="w-4 h-4" />
                            <span>PG Management</span>
                          </Link>
                        )}

                        {isAdmin && (
                          <Link
                            href="/admin"
                            onClick={() => setProfileDropdownOpen(false)}
                            className="flex items-center space-x-2.5 px-3 py-2 rounded-lg text-amber-700 hover:bg-amber-50 font-medium transition-colors"
                          >
                            <ShieldAlert className="w-4 h-4" />
                            <span>Admin Console</span>
                          </Link>
                        )}

                        <div className="my-1 border-t border-slate-100" />

                        <button
                          onClick={() => {
                            setProfileDropdownOpen(false);
                            logout();
                            router.push("/");
                          }}
                          className="w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg text-rose-600 hover:bg-rose-50 transition-colors text-left"
                        >
                          <LogOut className="w-4 h-4" />
                          <span>Sign Out</span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex items-center space-x-2">
                <Link href="/login">
                  <Button variant="ghost" size="sm">
                    Log in
                  </Button>
                </Link>
                <Link href="/register">
                  <Button variant="primary" size="sm">
                    Get Started
                  </Button>
                </Link>
              </div>
            )}
          </div>

          {/* Mobile Hamburger Button */}
          <div className="flex lg:hidden items-center space-x-2">
            {isAuthenticated && (
              <Link
                href="/messages"
                className="p-2 text-charcoal-light hover:text-forest relative"
                aria-label="Messages"
              >
                <MessageSquare className="w-5 h-5" />
              </Link>
            )}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-xl text-charcoal hover:bg-slate-100"
              aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
              aria-expanded={mobileMenuOpen}
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-b border-warm-200 bg-white px-4 pt-3 pb-6 space-y-2 animate-in fade-in duration-200">
          {navLinks.map((item) => {
            if (item.authOnly && !isAuthenticated) return null;
            const Icon = item.icon;
            const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center space-x-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition-colors ${
                  isActive
                    ? "text-forest bg-pale-green/40"
                    : "text-charcoal hover:bg-slate-100"
                }`}
              >
                <Icon className={`w-5 h-5 ${isActive ? "text-forest" : "text-charcoal-muted"}`} />
                <span>{item.label}</span>
              </Link>
            );
          })}

          {isAuthenticated && (
            <div className="pt-3 border-t border-slate-100 space-y-1">
              <span className="text-[11px] font-bold uppercase tracking-wider text-charcoal-muted px-3 block mb-1">
                Account & Roles
              </span>
              <Link
                href="/profile"
                onClick={() => setMobileMenuOpen(false)}
                className="flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-sm font-medium text-charcoal hover:bg-slate-100"
              >
                <UserCircle className="w-5 h-5 text-charcoal-muted" />
                <span>Profile & Lifestyle</span>
              </Link>

              {isOwner && (
                <Link
                  href="/owner"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-sm font-medium text-secondary-green hover:bg-pale-green/20"
                >
                  <Building className="w-5 h-5" />
                  <span>Owner Dashboard</span>
                </Link>
              )}

              {isTenant && (
                <Link
                  href="/tenants"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-sm font-medium text-secondary-green hover:bg-pale-green/20"
                >
                  <KeyRound className="w-5 h-5" />
                  <span>Tenant Vacancies</span>
                </Link>
              )}

              {isPG && (
                <Link
                  href="/pg"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-sm font-medium text-secondary-green hover:bg-pale-green/20"
                >
                  <Building className="w-5 h-5" />
                  <span>PG Operator</span>
                </Link>
              )}

              {isAdmin && (
                <Link
                  href="/admin"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-sm font-medium text-amber-700 hover:bg-amber-50"
                >
                  <ShieldAlert className="w-5 h-5" />
                  <span>Admin Console</span>
                </Link>
              )}

              <button
                onClick={() => {
                  setMobileMenuOpen(false);
                  logout();
                  router.push("/");
                }}
                className="w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-sm font-medium text-rose-600 hover:bg-rose-50 text-left"
              >
                <LogOut className="w-5 h-5" />
                <span>Sign Out</span>
              </button>
            </div>
          )}

          {!isAuthenticated && (
            <div className="pt-3 border-t border-slate-100 flex flex-col space-y-2">
              <Link href="/login" onClick={() => setMobileMenuOpen(false)}>
                <Button variant="outline" className="w-full justify-center">
                  Log in
                </Button>
              </Link>
              <Link href="/register" onClick={() => setMobileMenuOpen(false)}>
                <Button variant="primary" className="w-full justify-center">
                  Get Started
                </Button>
              </Link>
            </div>
          )}
        </div>
      )}
    </nav>
  );
};
