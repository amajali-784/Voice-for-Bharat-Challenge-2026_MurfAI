import { Mukta, Public_Sans } from 'next/font/google';
import localFont from 'next/font/local';
import { headers } from 'next/headers';
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
          <header className="fixed top-0 left-0 z-50 hidden w-full flex-row justify-between p-6 md:flex">
            <a
              target="_blank"
              rel="noopener noreferrer"
              href="https://murf.ai/api"
              className="text-foreground flex scale-100 items-center gap-2 transition-transform duration-300 hover:scale-110"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 64 64"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                className="text-[var(--primary)]"
              >
                <path
                  d="M32 56C32 56 12 42 12 24C12 16.5 17.5 11 25 11C29.2 11 32.6 13 32 17C33.4 13 36.8 11 39 11C46.5 11 52 16.5 52 24C52 42 32 56 32 56Z"
                  fill="currentColor"
                />
              </svg>
              <span className="font-mono text-xs font-bold tracking-wider uppercase">
                Swasthya Sahayak
              </span>
            </a>
            <span className="text-foreground font-mono text-xs font-bold tracking-wider uppercase">
              Powered by{' '}
              <a
                target="_blank"
                rel="noopener noreferrer"
                href="https://murf.ai/api/docs/text-to-speech/streaming"
                className="underline underline-offset-4"
              >
                Murf Falcon
              </a>
            </span>
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
