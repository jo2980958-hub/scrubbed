import { pounds } from '../../lib/money';
import { fmtDay } from '../../lib/dates';
import { Card, ReadinessPill, SectionTitle, riskWord } from '../ui';
import { Icon } from '../icons';
import InstrumentAudit from './InstrumentAudit';
import type { CaseDetail, ChecklistItem, ReadinessItem } from '../../api/types';

function roleInitials(name: string) {
  return name
    .replace(/^(Mr|Ms|Mrs|Dr|Prof)\.?\s+/i, '')
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('');
}

function ReadinessRow({ item }: { item: ReadinessItem }) {
  const icon = item.state === 'done' ? 'check' : item.state === 'blocked' ? 'alert' : 'clock';
  return (
    <li className={`ready-item ${item.state}`}>
      <span className="ready-mark" aria-hidden="true"><Icon name={icon} size={14} /></span>
      <div>
        <span className="ready-label">{item.label}</span>
        {item.detail && <span className="ready-detail muted">{item.detail}</span>}
      </div>
    </li>
  );
}

const PHASE_LABEL = { 'sign-in': 'Sign in', 'time-out': 'Time out', 'sign-out': 'Sign out' } as const;

function ChecklistPhase({ phase, items }: { phase: ChecklistItem['phase']; items: ChecklistItem[] }) {
  const done = items.filter((i) => i.done).length;
  return (
    <div className="phase">
      <div className="phase-head">
        <b>{PHASE_LABEL[phase]}</b>
        <span className="muted num">{done}/{items.length}</span>
      </div>
      <ul className="phase-list">
        {items.map((i) => (
          <li key={i.key} className={i.done ? 'done' : ''}>
            <span className="tick" aria-hidden="true">{i.done ? <Icon name="check" size={13} /> : null}</span>
            {i.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function CaseOverview({ detail }: { detail: CaseDetail }) {
  const { team, patient, readiness, checklist, tray } = detail;
  const phases: ChecklistItem['phase'][] = ['sign-in', 'time-out', 'sign-out'];
  const items = readiness.items ?? [];

  return (
    <div className="detail-grid">
      <Card>
        <SectionTitle title="Readiness" action={<ReadinessPill readiness={readiness} />} />
        <div className="readiness-score">
          <div className="score-bar" role="img" aria-label={`Readiness ${readiness.score} out of 100`}>
            <span className={`score-fill ready-${readiness.isReady ? 'ready' : readiness.risk}`} style={{ width: `${readiness.score}%` }} />
          </div>
          <div className="score-meta">
            <b className="num">{readiness.score}<span className="muted">/100</span></b>
            <span className="muted">{riskWord(readiness.risk)}</span>
          </div>
        </div>
        {items.length > 0 && <ul className="ready-list">{items.map((i) => <ReadinessRow key={i.key} item={i} />)}</ul>}
      </Card>

      <Card>
        <SectionTitle title="Patient" />
        <div className="patient">
          <div className="patient-id">
            <b>{patient.name}</b>
            <span className="muted">
              {patient.mrn}{patient.dateOfBirth ? ` · DOB ${fmtDay(patient.dateOfBirth)}` : ''}
            </span>
          </div>
          <div className={`balance ${patient.balancePence > 0 ? 'owed' : 'clear'}`}>
            <span className="muted">Patient balance</span>
            <b className="num">{pounds(patient.balancePence)}</b>
            <span className="balance-note">{patient.balancePence > 0 ? 'Outstanding. Tracked, not collected here' : 'Cleared'}</span>
          </div>
        </div>
      </Card>

      <Card>
        <SectionTitle title="Team" hint={`${team.length} on this case`} />
        <ul className="team-list">
          {team.map((m) => (
            <li key={m.staffId}>
              <span className="avatar sm" aria-hidden="true">{roleInitials(m.name)}</span>
              <div>
                <b>{m.name}</b>
                <span className="muted">{m.role}</span>
              </div>
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <SectionTitle title="Pre-op checklist" hint="WHO-style sign-in, time-out and sign-out" />
        <div className="checklist">
          {phases.map((p) => (
            <ChecklistPhase key={p} phase={p} items={checklist.items.filter((i) => i.phase === p)} />
          ))}
        </div>
      </Card>

      <div className="detail-full">
        <InstrumentAudit tray={tray} />
      </div>
    </div>
  );
}
