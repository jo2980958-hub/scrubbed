import { usePages } from '../../api/hooks';
import { fmtTime, fromNow } from '../../lib/dates';
import { Card, DeliveryChip, EmptyState, ErrorState, SectionTitle, Skeleton } from '../ui';
import { Icon } from '../icons';
import type { PageRecipient } from '../../api/types';

const STEPS: { key: keyof PageRecipient; label: string }[] = [
  { key: 'sentAt', label: 'Sent' },
  { key: 'deliveredAt', label: 'Delivered' },
  { key: 'readAt', label: 'Read' },
  { key: 'acknowledgedAt', label: 'Acknowledged' },
];

function roleInitials(name: string) {
  return name
    .replace(/^(Mr|Ms|Mrs|Dr|Prof)\.?\s+/i, '')
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('');
}

function RecipientRow({ r }: { r: PageRecipient }) {
  return (
    <div className={`ladder-row ${r.escalated ? 'escalated' : ''}`}>
      <div className="ladder-who">
        <span className="avatar sm" aria-hidden="true">{roleInitials(r.name)}</span>
        <div>
          <b>{r.name}</b>
          <span className="muted">{r.role}</span>
        </div>
      </div>
      <div className="ladder-track" aria-hidden="true">
        {STEPS.map((s) => {
          const at = r[s.key] as string | null | undefined;
          return (
            <span key={s.label} className={`track-step ${at ? 'hit' : ''}`} title={at ? `${s.label} ${fmtTime(at)}` : `${s.label}: not yet`}>
              <i />
              <small>{s.label}</small>
              <em>{at ? fmtTime(at) : '·'}</em>
            </span>
          );
        })}
      </div>
      <div className="ladder-end">
        <DeliveryChip status={r.status} escalated={r.escalated} />
        {r.escalated && r.escalatedAt && <span className="muted esc-time">Voice call {fromNow(r.escalatedAt)}</span>}
      </div>
    </div>
  );
}

export default function PagingLadder({ caseId }: { caseId: string }) {
  const pages = usePages(caseId);

  if (pages.isLoading) return <Card><Skeleton h={30} w="40%" /><div style={{ height: 14 }} /><Skeleton h={120} /></Card>;
  if (pages.isError) return <ErrorState error={pages.error} retry={() => pages.refetch()} />;
  const list = pages.data ?? [];
  if (list.length === 0) {
    return (
      <Card>
        <EmptyState icon="page" title="No pages sent yet" body="When a page fires, every team member appears here with their sent, delivered, read and acknowledged times, and whether they were escalated to a voice call." />
      </Card>
    );
  }

  return (
    <div className="stack">
      {list.map((p) => {
        const acked = p.recipients.filter((r) => r.status === 'acknowledged').length;
        const escalated = p.recipients.filter((r) => r.escalated).length;
        return (
          <Card key={p.pageId}>
            <SectionTitle
              title={p.urgent ? 'Urgent page' : 'Page'}
              hint={`${fmtTime(p.createdAt)} · ${acked}/${p.recipients.length} acknowledged${escalated ? ` · ${escalated} escalated` : ''}`}
              action={p.urgent ? <span className="chip alert"><Icon name="alert" size={13} />Urgent</span> : undefined}
            />
            <p className="page-body">{p.body}</p>
            <div className="ladder">
              {p.recipients.map((r) => <RecipientRow key={r.staffId ?? r.name} r={r} />)}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
