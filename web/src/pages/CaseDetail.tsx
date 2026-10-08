import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useCase } from '../api/hooks';
import { fmtDay, fmtTime } from '../lib/dates';
import { Button, ErrorState, ReadinessPill, Skeleton, usePageTitle } from '../components/ui';
import { Icon } from '../components/icons';
import CaseOverview from '../components/case/CaseOverview';
import PagingLadder from '../components/case/PagingLadder';
import CaseConversations from '../components/case/CaseConversations';
import CaseForms from '../components/case/CaseForms';
import PageDialog from '../components/PageDialog';

type Tab = 'overview' | 'paging' | 'conversations' | 'forms';
const TABS: { key: Tab; label: string; icon: 'board' | 'page' | 'chat' | 'forms' }[] = [
  { key: 'overview', label: 'Overview', icon: 'board' },
  { key: 'paging', label: 'Paging ladder', icon: 'page' },
  { key: 'conversations', label: 'Conversations', icon: 'chat' },
  { key: 'forms', label: 'Forms', icon: 'forms' },
];

const STAGE_LABEL: Record<string, string> = {
  scheduled: 'Scheduled',
  'in-theatre': 'In theatre',
  recovery: 'Recovery',
  complete: 'Complete',
};

export default function CaseDetail() {
  const { id = '' } = useParams();
  const [tab, setTab] = useState<Tab>('overview');
  const [paging, setPaging] = useState(false);
  const q = useCase(id);
  usePageTitle(q.data?.case.procedure ?? 'Case');

  return (
    <div className="page">
      <Link to="/" className="back"><Icon name="arrowLeft" size={16} />Case board</Link>

      {q.isLoading ? (
        <>
          <Skeleton h={40} w="55%" />
          <div style={{ height: 20 }} />
          <Skeleton h={220} />
        </>
      ) : q.isError ? (
        <ErrorState error={q.error} retry={() => q.refetch()} />
      ) : q.data ? (
        <>
          <div className="page-head case-head">
            <div>
              <div className="case-title">
                <h1>{q.data.case.procedure}</h1>
                {q.data.case.procedureCode && <span className="code">{q.data.case.procedureCode}</span>}
              </div>
              <div className="case-meta">
                <span><Icon name="theatre" size={15} />{q.data.case.theatre}</span>
                <span><Icon name="clock" size={15} />{fmtDay(q.data.case.scheduledAt)}, {fmtTime(q.data.case.scheduledAt)}</span>
                <span><Icon name="user" size={15} />{q.data.case.surgeonName}</span>
                {q.data.case.anaesthetic && <span><Icon name="info" size={15} />{q.data.case.anaesthetic}</span>}
                {q.data.case.stage && <span className="stage">{STAGE_LABEL[q.data.case.stage] ?? q.data.case.stage}</span>}
              </div>
            </div>
            <div className="head-actions">
              <ReadinessPill readiness={q.data.readiness} />
              <Button variant="primary" icon="page" onClick={() => setPaging(true)}>Page the team</Button>
            </div>
          </div>

          {q.data.case.notes && (
            <div className="banner info note">
              <Icon name="info" size={18} />
              <span>{q.data.case.notes}</span>
            </div>
          )}

          <div className="tabs" role="tablist" aria-label="Case sections">
            {TABS.map((t) => (
              <button key={t.key} role="tab" aria-selected={tab === t.key} className={`tab ${tab === t.key ? 'active' : ''}`} onClick={() => setTab(t.key)}>
                <Icon name={t.icon} size={16} />
                {t.label}
              </button>
            ))}
          </div>

          <div className="tab-panel" role="tabpanel">
            {tab === 'overview' && <CaseOverview detail={q.data} />}
            {tab === 'paging' && <PagingLadder caseId={id} />}
            {tab === 'conversations' && <CaseConversations caseId={id} />}
            {tab === 'forms' && <CaseForms caseId={id} />}
          </div>

          <PageDialog caseId={id} open={paging} onClose={() => setPaging(false)} />
        </>
      ) : null}
    </div>
  );
}
