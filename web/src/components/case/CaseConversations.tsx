import { useMemo } from 'react';
import { useConversations } from '../../api/hooks';
import { fmtTime } from '../../lib/dates';
import { Card, EmptyState, ErrorState, SectionTitle, Skeleton } from '../ui';
import { Icon } from '../icons';
import type { Message } from '../../api/types';

function Bubble({ m }: { m: Message }) {
  const out = m.direction === 'out';
  return (
    <div className={`bubble-row ${out ? 'out' : 'in'}`}>
      <div className="bubble">
        {m.kind && m.kind !== 'text' && (
          <span className="bubble-kind">
            <Icon name={m.kind === 'image' ? 'tray' : m.kind === 'document' ? 'forms' : m.kind === 'audio' ? 'page' : 'chat'} size={12} />
            {m.kind}
          </span>
        )}
        <span className="bubble-body">{m.body}</span>
        <span className="bubble-meta">
          {fmtTime(m.createdAt)}
          {out && (m.readAt ? <span className="read" title={`Read ${fmtTime(m.readAt)}`}><Icon name="check" size={12} />Read</span> : <span className="muted">Sent</span>)}
        </span>
      </div>
    </div>
  );
}

export default function CaseConversations({ caseId }: { caseId: string }) {
  const conv = useConversations(caseId);
  const groups = useMemo(() => {
    const map = new Map<string, { name: string; role?: string; number: string; messages: Message[] }>();
    for (const m of conv.data ?? []) {
      const g = map.get(m.number) ?? { name: m.name, role: m.role, number: m.number, messages: [] };
      g.messages.push(m);
      map.set(m.number, g);
    }
    return [...map.values()];
  }, [conv.data]);

  if (conv.isLoading) return <Card><Skeleton h={30} w="40%" /><div style={{ height: 14 }} /><Skeleton h={160} /></Card>;
  if (conv.isError) return <ErrorState error={conv.error} retry={() => conv.refetch()} />;
  if (groups.length === 0) {
    return <Card><EmptyState icon="chat" title="No messages yet" body="Every message in and out for this case appears here, per person, with read times." /></Card>;
  }

  return (
    <div className="stack">
      {groups.map((g) => (
        <Card key={g.number}>
          <SectionTitle title={g.name} hint={`${g.role ?? 'Contact'} · ${g.number}`} />
          <div className="thread">
            {g.messages.map((m, i) => <Bubble key={`${g.number}-${i}`} m={m} />)}
          </div>
        </Card>
      ))}
    </div>
  );
}
