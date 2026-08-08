import { Mukta, Public_Sans } from 'next/font/google';
import localFont from 'next/font/local';
import { headers } from 'next/headers';
import Link from 'next/link';
import { ThemeProvider } from '@/components/app/theme-provider';
import { ThemeToggle } from '@/components/app/theme-toggle';
import { cn } from '@/lib/shadcn/utils';
import { getAppConfig, getStyles } from '@/lib/utils';
import '@/styles/globals.css';

const publicSans = Public_Sans({
  variable: '--font-public-sans',
  subsets: ['latin'],
});

const mukta = Mukta({
  variable: '--font-mukta',
  subsets: ['latin', 'devanagari'],
  weight: ['400', '600', '700'],
});

const commitMono = localFont({
  display: 'swap',
  variable: '--font-commit-mono',
  src: [
    {
      path: '../fonts/CommitMono-400-Regular.otf',
      weight: '400',
      style: 'normal',
    },
    {
      path: '../fonts/CommitMono-700-Regular.otf',
      weight: '700',
      style: 'normal',
    },
    {
      path: '../fonts/CommitMono-400-Italic.otf',
      weight: '400',
      style: 'italic',
    },
    {
      path: '../fonts/CommitMono-700-Italic.otf',
      weight: '700',
      style: 'italic',
    },
  ],
});

interface RootLayoutProps {
  children: React.ReactNode;
}

export default async function RootLayout({ children }: RootLayoutProps) {
  const hdrs = await headers();
  const appConfig = await getAppConfig(hdrs);
  const styles = getStyles(appConfig);
  const { pageTitle, pageDescription } = appConfig;

  return (
    <html
      lang="hi"
      suppressHydrationWarning
      className={cn(
        publicSans.variable,
        mukta.variable,
        commitMono.variable,
        'scroll-smooth font-sans antialiased'
      )}
    >
      <head>
        {styles && <style>{styles}</style>}
        <title>{pageTitle}</title>
        <meta name="description" content={pageDescription} />
      </head>
      <body className="overflow-x-hidden">
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <header className="fixed top-0 left-0 z-50 flex w-full flex-row items-center justify-between gap-2 p-4 md:p-6">
            <Link href="/" className="group flex items-center gap-3">
              <span className="bg-forest shadow-forest/20 dark:bg-sage flex size-10 shrink-0 items-center justify-center rounded-2xl shadow-lg transition-transform duration-300 group-hover:scale-110">
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
                    fill="#fff9ed"
                  />
                  <path
                    d="M24 30H40M32 22V38"
                    stroke="#28543d"
                    strokeWidth="4"
                    strokeLinecap="round"
                  />
                </svg>
              </span>
              <span className="flex flex-col leading-tight">
                <span
                  className="text-foreground text-base font-bold"
                  style={{ fontFamily: 'var(--font-mukta)' }}
                >
                  स्वास्थ्य सहायक
                </span>
                <span className="text-muted-foreground font-mono text-[9px] font-bold tracking-wider uppercase">
                  Swasthya Sahayak · Health Voice Agent
                </span>
              </span>
            </Link>

            <div className="flex items-center gap-3">
              <span className="border-border bg-card/70 text-muted-foreground hidden items-center gap-1.5 rounded-full border px-3 py-1.5 font-mono text-[10px] font-bold tracking-wider uppercase sm:inline-flex">
                <span className="text-sage">हिंदी</span>
                <span className="opacity-40">|</span>
                English
              </span>
              <span className="text-foreground hidden font-mono text-xs font-bold tracking-wider uppercase md:inline">
                Powered by{' '}
                <a
                  target="_blank"
                  rel="noopener noreferrer"
                  href="https://murf.ai/api/docs/text-to-speech/streaming"
                  className="text-sage hover:text-forest dark:text-sage-light underline underline-offset-4"
                >
                  Murf Falcon
                </a>
              </span>
            </div>
          </header>

          {children}
          <div className="group fixed bottom-0 left-1/2 z-50 mb-2 -translate-x-1/2">
            <ThemeToggle className="translate-y-20 transition-transform delay-150 duration-300 group-hover:translate-y-0" />
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
