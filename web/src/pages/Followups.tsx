import { useMemo } from 'react';
import { useFollowups } from '../api/hooks';
import { fmtDateTime, fromNow } from '../lib/dates';
import { Card, EmptyState, ErrorState, FollowupChip, SectionTitle, Skeleton, Stat, usePageTitle } from '../components/ui';
import { Icon } from '../components/icons';
import type { Followup, FollowupStatus } from '../api/types';

const ORDER: Record<FollowupStatus, number> = { escalated: 0, overdue: 1, due: 2, replied: 3, scheduled: 4, closed: 5 };

function Row({ f }: { f: Followup }) {
  const danger = f.status === 'escalated';
  return (
    <li className={`followup-row ${danger ? 'danger' : ''}`}>
      <div className="fu-main">
        <b>{f.patientName}</b>
        <span className="muted">{f.procedure}{f.surgeonName ? ` · ${f.surgeonName}` : ''}</span>
        {f.lastReply && (
          <span className={`fu-reply ${danger ? 'danger' : ''}`}>
            {danger && <Icon name="alert" size={13} />}
            “{f.lastReply}”
          </span>
        )}
      </div>
      <div className="fu-end">
        <FollowupChip status={f.status} />
        <span className="muted fu-due" title={fmtDateTime(f.dueAt)}>
          {f.status === 'scheduled' ? `Due ${fromNow(f.dueAt)}` : f.status === 'replied' ? `Replied ${fromNow(f.dueAt)}` : `${fromNow(f.dueAt)}`}
        </span>
      </div>
    </li>
  );
}

export default function Followups() {
  usePageTitle('Follow-up queue');
  const q = useFollowups();
  const list = q.data ?? [];
  const sorted = useMemo(() => [...list].sort((a, b) => ORDER[a.status] - ORDER[b.status] || a.dueAt.localeCompare(b.dueAt)), [list]);

  const escalated = list.filter((f) => f.status === 'escalated').length;
  const overdue = list.filter((f) => f.status === 'overdue').length;
  const due = list.filter((f) => f.status === 'due').length;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Follow-up queue</h1>
          <p className="muted">Post-op check-ins. Danger-sign replies escalate to the team. Scrubbed never diagnoses or reassures.</p>
        </div>
      </div>

      {list.length > 0 && (
        <div className="stat-row">
          <Stat label="Escalated" value={escalated} tone={escalated > 0 ? 'alert' : undefined} />
          <Stat label="Overdue" value={overdue} tone={overdue > 0 ? 'warn' : undefined} />
          <Stat label="Due now" value={due} />
        </div>
      )}

      {q.isLoading ? (
        <Card><Skeleton h={30} w="40%" /><div style={{ height: 14 }} /><Skeleton h={160} /></Card>
      ) : q.isError ? (
        <ErrorState error={q.error} retry={() => q.refetch()} />
      ) : list.length === 0 ? (
        <Card><EmptyState icon="followups" title="Nothing in the queue" body="Patients due for a post-op check-in will appear here." /></Card>
      ) : (
        <Card>
          <SectionTitle title="Patients" hint={`${list.length} in the queue`} />
          <ul className="followup-list">
            {sorted.map((f) => <Row key={f.caseId} f={f} />)}
          </ul>
        </Card>
      )}
    </div>
  );
}
