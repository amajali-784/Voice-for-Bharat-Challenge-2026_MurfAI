import { Button } from '@/components/ui/button';

function HealthIcon() {
  return (
    <svg
      width="72"
      height="72"
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="mb-4 size-16 text-[var(--primary)]"
    >
      <path
        d="M32 56C32 56 12 42 12 24C12 16.5 17.5 11 25 11C29.2 11 32.6 13 32 17C33.4 13 36.8 11 39 11C46.5 11 52 16.5 52 24C52 42 32 56 32 56Z"
        fill="currentColor"
      />
      <path
        d="M26 28H31V23C31 22.4 31.4 22 32 22C32.6 22 33 22.4 33 23V28H38C38.6 28 39 28.4 39 29C39 29.6 38.6 30 38 30H33V35C33 35.6 32.6 36 32 36C31.4 36 31 35.6 31 35V30H26C25.4 30 25 29.6 25 29C25 28.4 25.4 28 26 28Z"
        fill="white"
      />
    </svg>
  );
}

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  ref,
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  return (
    <div ref={ref}>
      <section
        className="bg-background flex flex-col items-center justify-center px-4 text-center"
        style={{ fontFamily: 'var(--font-mukta)' }}
      >
        <span className="mb-4 inline-flex items-center gap-2 rounded-full border border-[var(--primary)]/20 bg-[var(--primary)]/10 px-3 py-1 font-mono text-[11px] font-bold tracking-wider uppercase">
          <span className="size-1.5 rounded-full bg-[var(--primary)]" />
          Health Access · #VoiceForBharat
        </span>

        <HealthIcon />

        <h1 className="text-foreground text-3xl leading-tight font-bold tracking-tight md:text-4xl">
          स्वास्थ्य सहायक (Swasthya Sahayak - Health Voice Agent)
        </h1>
        <p className="text-muted-foreground mt-2 max-w-prose leading-6 font-medium">
          अपने स्वास्थ्य से जुड़े सवाल हिंदी में पूछें — लक्षण, नज़दीकी स्वास्थ्य केंद्र, और डॉक्टर
          से मिलने से पहले की सलाह।
        </p>
        <p className="text-muted-foreground mt-1 max-w-prose text-sm">
          Ask about symptoms, nearby health centres, and doctor guidance in Hindi.
        </p>

        <Button
          size="lg"
          onClick={onStartCall}
          className="mt-8 w-64 rounded-full font-mono text-xs font-bold tracking-wider uppercase"
        >
          {startButtonText}
        </Button>
      </section>

      <div className="fixed bottom-5 left-0 flex w-full items-center justify-center px-4">
        <p className="text-muted-foreground max-w-prose pt-1 text-center text-xs leading-5 font-normal text-pretty md:text-sm">
          ध्यान दें: यह एजेंट जानकारी के लिए है, डॉक्टर नहीं। गंभीर लक्षण होने पर तुरंत नज़दीकी
          अस्पताल या 108 पर कॉल करें।
        </p>
      </div>
    </div>
  );
};
