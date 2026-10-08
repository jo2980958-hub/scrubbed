import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import type { DeliveryStatus, FollowupStatus, FormStatus, Readiness, Risk } from '../api/types';
import { Icon, type IconName } from './icons';

/* ------------------------------------------------------------ readiness */

export function ReadinessPill({ readiness, showScore = true }: { readiness: Readiness; showScore?: boolean }) {
  const tone = readiness.isReady ? 'ready' : readiness.risk === 'high' ? 'high' : readiness.risk === 'low' ? 'low' : 'med';
  const label = readiness.isReady ? 'Ready' : 'At risk';
  return (
    <span className={`pill ready-${tone}`}>
      <span className="dot" aria-hidden="true" />
      {label}
      {showScore && <span className="pill-score">{readiness.score}</span>}
    </span>
  );
}

const RISK_WORD: Record<Risk, string> = { none: 'On track', low: 'Low risk', medium: 'Medium risk', high: 'High risk' };
export function riskWord(risk: Risk): string {
  return RISK_WORD[risk];
}

/* -------------------------------------------------------- status chips */

const DELIVERY: Record<DeliveryStatus, { label: string; tone: string }> = {
  queued: { label: 'Queued', tone: 'muted' },
  sent: { label: 'Sent', tone: 'muted' },
  delivered: { label: 'Delivered', tone: 'muted' },
  read: { label: 'Read', tone: 'info' },
  acknowledged: { label: 'Acknowledged', tone: 'ok' },
  failed: { label: 'Failed', tone: 'alert' },
};

export function DeliveryChip({ status, escalated }: { status: DeliveryStatus; escalated?: boolean }) {
  if (escalated || status === 'failed') {
    return <span className="chip alert"><Icon name="phone" size={13} />{escalated ? 'Escalated to call' : 'Failed'}</span>;
  }
  const d = DELIVERY[status];
  return <span className={`chip ${d.tone}`}>{d.label}</span>;
}

const FORM: Record<FormStatus, { label: string; tone: string }> = {
  requested: { label: 'Requested', tone: 'muted' },
  sent: { label: 'Sent', tone: 'info' },
  completed: { label: 'Completed', tone: 'ok' },
  overdue: { label: 'Overdue', tone: 'alert' },
};
export function FormChip({ status }: { status: FormStatus }) {
  const f = FORM[status];
  return <span className={`chip ${f.tone}`}>{f.label}</span>;
}

const FOLLOWUP: Record<FollowupStatus, { label: string; tone: string }> = {
  scheduled: { label: 'Scheduled', tone: 'muted' },
  due: { label: 'Due', tone: 'info' },
  overdue: { label: 'Overdue', tone: 'warn' },
  replied: { label: 'Replied', tone: 'ok' },
  escalated: { label: 'Escalated', tone: 'alert' },
  closed: { label: 'Closed', tone: 'muted' },
};
export function FollowupChip({ status }: { status: FollowupStatus }) {
  const f = FOLLOWUP[status];
  return <span className={`chip ${f.tone}`}>{f.label}</span>;
}

/* ------------------------------------------------------------- surfaces */

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>;
}

export function SectionTitle({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="section-title">
      <div>
        <h2>{title}</h2>
        {hint && <p className="muted">{hint}</p>}
      </div>
      {action}
    </div>
  );
}

export function Stat({ label, value, tone }: { label: string; value: ReactNode; tone?: 'alert' | 'ok' | 'warn' }) {
  return (
    <div className={`stat ${tone ?? ''}`}>
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

/* --------------------------------------------------------------- inputs */

export function Button({
  variant = 'secondary',
  size,
  loading,
  icon,
  children,
  className = '',
  ...rest
}: {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm';
  loading?: boolean;
  icon?: IconName;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...rest}
      type={rest.type ?? 'button'}
      disabled={rest.disabled || loading}
      className={`btn ${variant === 'secondary' ? '' : variant} ${size ?? ''} ${className}`}
    >
      {loading ? <span className="spinner" aria-hidden="true" /> : icon ? <Icon name={icon} size={16} /> : null}
      {children}
    </button>
  );
}

export function Field({
  label,
  hint,
  error,
  children,
  full,
  htmlFor,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
  full?: boolean;
  htmlFor: string;
}) {
  return (
    <div className={`field ${full ? 'full' : ''}`}>
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {hint && !error && <span className="hint" id={`${htmlFor}-hint`}>{hint}</span>}
      {error && <span className="field-err" id={`${htmlFor}-err`} role="alert">{error}</span>}
    </div>
  );
}

/* --------------------------------------------------------------- states */

export function Skeleton({ h = 20, w = '100%' }: { h?: number; w?: number | string }) {
  return <div className="skeleton" style={{ height: h, width: w }} aria-hidden="true" />;
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div className="banner alert" role="alert">
      <Icon name="alert" size={18} />
      <div style={{ flex: 1 }}>
        <b>We could not load this.</b>
        <div className="muted">{error instanceof Error ? error.message : 'Something went wrong.'}</div>
      </div>
      {retry && <Button size="sm" onClick={retry}>Try again</Button>}
    </div>
  );
}

export function EmptyState({ icon = 'info', title, body, action }: { icon?: IconName; title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-icon" aria-hidden="true"><Icon name={icon} size={24} /></div>
      <b>{title}</b>
      {body && <p className="muted">{body}</p>}
      {action}
    </div>
  );
}

/* --------------------------------------------------------------- toasts */

interface Toast { id: number; text: string; kind: 'ok' | 'err' }
const ToastCtx = createContext<(text: string, kind?: Toast['kind']) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, kind: Toast['kind'] = 'ok') => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, text, kind }]);
    window.setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 4800);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast ${t.kind === 'err' ? 'err' : ''}`}>
            <Icon name={t.kind === 'err' ? 'alert' : 'check'} size={16} />
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

/* --------------------------------------------------------------- dialog */

export function Dialog({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      aria-labelledby="dlg-title"
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      {open && (
        <div className="dlg">
          <h2 id="dlg-title">{title}</h2>
          {children}
        </div>
      )}
    </dialog>
  );
}

export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = `${title} · Scrubbed`;
  }, [title]);
}
