'use client';

import Link from 'next/link';
import { type AppLanguage, useLanguage } from '@/components/app/language-provider';
import { cn } from '@/lib/shadcn/utils';

const LANGUAGES: { value: AppLanguage; label: string }[] = [
  { value: 'en', label: 'EN' },
  { value: 'hi', label: 'हि' },
];

export function GlassHeader() {
  const { language, setLanguage } = useLanguage();

  return (
    <header className="fixed inset-x-0 top-0 z-50 p-3 md:p-4">
      <div className="glass-panel mx-auto flex w-full max-w-7xl items-center justify-between gap-2 rounded-2xl px-3 py-2.5 md:px-5">
        <Link href="/" className="group flex min-w-0 flex-1 items-center gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-b from-teal-400/80 to-cyan-500/70 shadow-[0_0_24px_rgba(45,212,191,0.4)] transition-transform duration-300 group-hover:scale-110">
            <svg
              width="22"
              height="22"
              viewBox="0 0 64 64"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden
            >
              <path
                d="M32 50C32 50 13 38 13 23C13 16.5 18 11.5 24.5 11.5C28.2 11.5 31.2 13.4 32 16.5C32.8 13.4 35.8 11.5 39.5 11.5C46 11.5 51 16.5 51 23C51 38 32 50 32 50Z"
                fill="#06201a"
              />
              <path d="M24 30H40M32 22V38" stroke="#5eead4" strokeWidth="4" strokeLinecap="round" />
            </svg>
          </span>
          <span className="flex min-w-0 flex-col leading-tight">
            <span
              className="text-foreground truncate text-base font-bold"
              style={{ fontFamily: 'var(--font-mukta)' }}
            >
              स्वास्थ्य सहायक
            </span>
            <span className="text-muted-foreground truncate font-mono text-[9px] font-bold tracking-wider uppercase">
              Swasthya Sahayak · Health Voice Agent
            </span>
          </span>
        </Link>

        <div className="flex shrink-0 items-center gap-2 md:gap-3">
          <Link
            href="/escalations"
            className="glass-chip text-muted-foreground hover:text-foreground hidden items-center gap-1.5 rounded-full px-3 py-1.5 font-mono text-[10px] font-bold tracking-wider uppercase transition-colors sm:inline-flex"
          >
            <span className="text-teal-400">मानव सहायता</span>
            <span className="opacity-40">|</span>
            Human Help
          </Link>
          <Link
            href="/analytics"
            className="glass-chip text-muted-foreground hover:text-foreground hidden items-center gap-1.5 rounded-full px-3 py-1.5 font-mono text-[10px] font-bold tracking-wider uppercase transition-colors md:inline-flex"
          >
            <span className="text-teal-400">विश्लेषण</span>
            <span className="opacity-40">|</span>
            Analytics
          </Link>

          {/* Bilingual language selector EN | HI */}
          <div
            className="glass-chip flex items-center rounded-full p-1"
            role="group"
            aria-label="Interface language"
          >
            {LANGUAGES.map(({ value, label }) => (
              <button
                key={value}
                type="button"
                onClick={() => setLanguage(value)}
                aria-pressed={language === value}
                className={cn(
                  'rounded-full px-2.5 py-1 font-mono text-[11px] font-bold tracking-wider transition-all',
                  language === value
                    ? 'bg-teal-400/90 text-teal-950 shadow-[0_0_16px_rgba(45,212,191,0.45)]'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {label}
              </button>
            ))}
          </div>

          <span className="text-foreground hidden font-mono text-xs font-bold tracking-wider uppercase lg:inline">
            Powered by{' '}
            <a
              target="_blank"
              rel="noopener noreferrer"
              href="https://murf.ai/api/docs/text-to-speech/streaming"
              className="text-teal-400 underline underline-offset-4 hover:text-teal-300"
            >
              Murf Falcon
            </a>
          </span>
        </div>
      </div>
    </header>
  );
}
