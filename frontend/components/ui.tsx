// Prymitywy UI — Tailwind v4 na tokenach (dark-ops), bez bibliotek.
// Kolory: bg / surface / surface-2 / border / fg / fg-muted / accent / danger / warn.

import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from "react";

type Variant = "primary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-accent text-bg hover:bg-accent-strong shadow-[0_0_0_1px_rgba(34,197,94,0.25)] hover:shadow-[0_0_16px_-2px_rgba(34,197,94,0.45)] disabled:bg-accent/40 disabled:shadow-none disabled:cursor-not-allowed",
  ghost:
    "bg-surface-2 text-fg hover:bg-border disabled:opacity-40 disabled:cursor-not-allowed",
  danger:
    "bg-danger/10 text-danger hover:bg-danger/20 disabled:opacity-40 disabled:cursor-not-allowed",
};

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-all duration-150 ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}

const INPUT_CLS =
  "rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-fg placeholder:text-fg-subtle outline-none transition-colors duration-150 focus:border-accent";

export function Field({
  label,
  hint,
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium text-fg-muted">{label}</span>
      <input className={`${INPUT_CLS} ${className}`} {...props} />
      {hint && <span className="text-xs text-fg-subtle">{hint}</span>}
    </label>
  );
}

export function Select({
  label,
  className = "",
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { label?: string }) {
  const select = (
    <select className={`${INPUT_CLS} cursor-pointer ${className}`} {...props}>
      {children}
    </select>
  );
  if (!label) return select;
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium text-fg-muted">{label}</span>
      {select}
    </label>
  );
}

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-border bg-surface p-4 ${className}`}
    >
      {children}
    </div>
  );
}

type Tone = "accent" | "danger" | "warn" | "muted";

const TONES: Record<Tone, string> = {
  accent: "bg-accent/10 text-accent",
  danger: "bg-danger/10 text-danger",
  warn: "bg-warn/10 text-warn",
  muted: "bg-surface-2 text-fg-muted",
};

export function Badge({
  tone = "muted",
  className = "",
  children,
}: {
  tone?: Tone;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${TONES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
      {message}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-fg-muted">
      <span className="size-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      {label ?? "Ładowanie…"}
    </div>
  );
}
