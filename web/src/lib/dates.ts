const TZ = 'en-GB';

/** 2026-10-08T14:00:00Z -> "14:00". */
export function fmtTime(iso?: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString(TZ, { hour: '2-digit', minute: '2-digit', hour12: false });
}

/** 2026-10-08 -> "Thu 8 Oct". */
export function fmtDay(iso?: string | null): string {
  if (!iso) return '';
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString(TZ, { weekday: 'short', day: 'numeric', month: 'short' });
}

/** 2026-10-08T14:00:00Z -> "Thu 8 Oct, 14:00". */
export function fmtDateTime(iso?: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return `${fmtDay(iso)}, ${fmtTime(iso)}`;
}

/** A terse relative time, e.g. "4 min ago", "in 2 h", "now". */
export function fromNow(iso?: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const diffMs = d.getTime() - Date.now();
  const past = diffMs < 0;
  const mins = Math.round(Math.abs(diffMs) / 60000);
  if (mins < 1) return 'now';
  const label = (n: number, unit: string) => (past ? `${n} ${unit} ago` : `in ${n} ${unit}`);
  if (mins < 60) return label(mins, mins === 1 ? 'min' : 'min');
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return label(hrs, hrs === 1 ? 'hour' : 'hours');
  const days = Math.round(hrs / 24);
  return label(days, days === 1 ? 'day' : 'days');
}

/** Today's date as YYYY-MM-DD in local time. */
export function todayIso(): string {
  const d = new Date();
  const z = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}

/** Add days to a YYYY-MM-DD string. */
export function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  const z = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}
