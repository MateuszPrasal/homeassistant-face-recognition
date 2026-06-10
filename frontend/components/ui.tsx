// Drobne prymitywy UI — Tailwind, bez bibliotek.

import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-blue-600 text-white hover:bg-blue-500 disabled:bg-blue-600/40 disabled:cursor-not-allowed",
  ghost:
    "bg-black/5 dark:bg-white/10 hover:bg-black/10 dark:hover:bg-white/20 disabled:opacity-40",
  danger:
    "bg-red-600/10 text-red-600 dark:text-red-400 hover:bg-red-600/20 disabled:opacity-40",
};

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}

export function Field({
  label,
  hint,
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium opacity-80">{label}</span>
      <input
        className={`rounded-md border border-black/15 dark:border-white/15 bg-transparent px-2.5 py-1.5 outline-none focus:border-blue-500 ${className}`}
        {...props}
      />
      {hint && <span className="text-xs opacity-50">{hint}</span>}
    </label>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] p-4 ${className}`}
    >
      {children}
    </div>
  );
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">
      {message}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm opacity-60">
      <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      {label ?? "Ładowanie…"}
    </div>
  );
}
