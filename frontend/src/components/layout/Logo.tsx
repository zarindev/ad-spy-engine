import { cn } from "@/lib/utils";

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={cn("size-8", className)} aria-hidden>
      <defs>
        <linearGradient id="lm" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#8B5CF6" />
          <stop offset="1" stopColor="#6D28D9" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill="url(#lm)" />
      <circle cx="28" cy="28" r="13" fill="none" stroke="#fff" strokeWidth="5" />
      <path d="M38 38l10 10" stroke="#fff" strokeWidth="6" strokeLinecap="round" />
      <circle cx="28" cy="28" r="4.5" fill="#F59E0B" />
    </svg>
  );
}
