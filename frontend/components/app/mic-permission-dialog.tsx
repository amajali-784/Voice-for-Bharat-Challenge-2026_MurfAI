'use client';

import { useEffect } from 'react';
import { MicOff, RefreshCw, ShieldAlert, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { Button } from '@/components/ui/button';

interface MicPermissionDialogProps {
  open: boolean;
  onClose: () => void;
  onRetry: () => void;
}

const STEPS = [
  {
    en: 'Click the padlock / mic icon in the address bar',
    hi: 'एड्रेस बार में 🔒 (पैडलॉक) या माइक आइकन पर क्लिक करें',
  },
  {
    en: 'Choose "Allow" for Microphone access',
    hi: 'Microphone के लिए "Allow" (अनुमति दें) चुनें',
  },
  {
    en: 'Then press "Try Again" below',
    hi: 'फिर नीचे "Try Again" (फिर कोशिश करें) दबाएँ',
  },
];

export function MicPermissionDialog({ open, onClose, onRetry }: MicPermissionDialogProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="bg-forest/50 fixed inset-0 z-[100] flex items-center justify-center p-4 backdrop-blur-sm dark:bg-black/60"
          onClick={onClose}
          role="dialog"
          aria-modal="true"
          aria-labelledby="mic-permission-title"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, translateY: 12 }}
            animate={{ opacity: 1, scale: 1, translateY: 0 }}
            exit={{ opacity: 0, scale: 0.95, translateY: 12 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            onClick={(e) => e.stopPropagation()}
            className="border-border bg-background w-full max-w-md rounded-[28px] border p-6 shadow-2xl"
          >
            <div className="flex items-start justify-between">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', stiffness: 300, damping: 18, delay: 0.1 }}
                className="bg-gold/15 text-gold relative flex size-14 items-center justify-center rounded-full"
              >
                <motion.span
                  aria-hidden
                  animate={{ scale: [1, 1.6], opacity: [0.3, 0] }}
                  transition={{ duration: 2.2, repeat: Infinity, ease: 'easeOut' }}
                  className="bg-gold/20 absolute inset-0 rounded-full"
                />
                <MicOff className="size-6" />
              </motion.div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="text-muted-foreground hover:bg-accent rounded-full p-2 transition-colors"
              >
                <X className="size-5" />
              </button>
            </div>

            <motion.h2
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15, duration: 0.3 }}
              id="mic-permission-title"
              className="text-foreground mt-4 text-xl font-bold"
              style={{ fontFamily: 'var(--font-mukta)' }}
            >
              माइक की अनुमति चाहिए · Microphone access needed
            </motion.h2>

            <p className="text-muted-foreground mt-2 text-sm leading-6">
              स्वास्थ्य सहायक को आपकी आवाज़ सुनने के लिए microphone access चाहिए — लेकिन ब्राउज़र ने
              इसे ब्लॉक कर दिया है।
            </p>
            <p className="text-muted-foreground mt-1 text-sm leading-6">
              Swasthya Sahayak needs microphone access to hear you, but your browser blocked it.
            </p>

            <ol className="mt-4 space-y-2">
              {STEPS.map((step, i) => (
                <motion.li
                  key={step.en}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.25 + i * 0.1, duration: 0.3 }}
                  className="flex items-start gap-3 text-sm"
                >
                  <span className="bg-sage/15 text-sage flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-bold">
                    {i + 1}
                  </span>
                  <span>
                    <span className="text-foreground font-medium">{step.hi}</span>
                    <span className="text-muted-foreground block text-xs">{step.en}</span>
                  </span>
                </motion.li>
              ))}
            </ol>

            <div className="border-gold/25 bg-gold/10 mt-4 flex items-start gap-2 rounded-2xl border p-3">
              <ShieldAlert className="text-terracotta mt-0.5 size-4 shrink-0 dark:text-amber-300" />
              <p className="text-terracotta text-xs leading-5 dark:text-amber-200">
                कुछ ब्राउज़रों में permission सिर्फ़ एड्रेस बार के पैडलॉक आइकन से बदलती है। अगर
                विकल्प न दिखे, तो साइट को नए टैब में खोलें।
                <span className="mt-1 block opacity-80">
                  On some browsers the permission can only be changed from the padlock icon next to
                  the address. If missing, open the site in a new tab.
                </span>
              </p>
            </div>

            <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-end">
              <Button variant="outline" onClick={onClose} className="rounded-full">
                बंद करें · Close
              </Button>
              <Button
                onClick={onRetry}
                className="rounded-full bg-[var(--primary)] font-semibold text-[var(--primary-foreground)] hover:bg-[var(--primary)]/90"
              >
                <RefreshCw className="size-4" />
                फिर कोशिश करें · Try Again
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
