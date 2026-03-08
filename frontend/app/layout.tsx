"use client";

import "./globals.css";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getToken, removeToken } from "@/lib/auth";

const NAV_ITEMS = [
  { label: "Chat", href: "/chat" },
  { label: "Voice", href: "/voice" },
  { label: "Dashboard", href: "/dashboard" },
  { label: "Settings", href: "/settings" },
];

const AUTH_PAGES = ["/login", "/register"];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const isAuthPage = AUTH_PAGES.includes(pathname);

  useEffect(() => {
    setMounted(true);
    const token = getToken();
    if (!token && !isAuthPage) {
      router.push("/login");
    }
  }, [pathname, isAuthPage, router]);

  if (!mounted) {
    return (
      <html lang="en">
        <head>
          <title>Eros AI — Your Companion</title>
          <meta name="description" content="Personal AI companion with deep memory and voice" />
        </head>
        <body>
          <div className="app-layout">
            <div className="app-content">{children}</div>
          </div>
        </body>
      </html>
    );
  }

  return (
    <html lang="en">
      <head>
        <title>Eros AI — Your Companion</title>
        <meta name="description" content="Personal AI companion with deep memory and voice" />
      </head>
      <body>
        <div className="app-layout">
          {!isAuthPage && (
            <nav className="navbar">
              <span className="navbar-brand">eros</span>
              <div className="navbar-links">
                {NAV_ITEMS.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`navbar-link ${pathname === item.href ? "active" : ""}`}
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
              <div className="navbar-actions">
                <button
                  className="navbar-avatar"
                  onClick={() => {
                    removeToken();
                    router.push("/login");
                  }}
                  title="Log out"
                >
                  ×
                </button>
              </div>
            </nav>
          )}
          <div className="app-content">{children}</div>
        </div>
      </body>
    </html>
  );
}
