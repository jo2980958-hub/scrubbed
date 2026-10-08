import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useCases } from '../api/hooks';
import { addDays, fmtDay, fmtTime, todayIso } from '../lib/dates';
import { Button, EmptyState, ErrorState, ReadinessPill, Skeleton, Stat, usePageTitle } from '../components/ui';
import { Icon } from '../components/icons';
import NewCaseDialog from '../components/NewCaseDialog';
import type { CaseSummary } from '../api/types';

export default function CaseBoard() {
  usePageTitle('Case board');
  const [day, setDay] = useState(todayIso());
  const [adding, setAdding] = useState(false);
  const cases = useCases(day);

  const list = cases.data ?? [];
  const theatres = useMemo(() => {
    const map = new Map<string, CaseSummary[]>();
    for (const c of list) {
      const arr = map.get(c.theatre) ?? [];
      arr.push(c);
      map.set(c.theatre, arr);
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [list]);

  const ready = list.filter((c) => c.readiness.isReady).length;
  const atRisk = list.length - ready;
  const isToday = day === todayIso();

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Case board</h1>
          <p className="muted">{isToday ? 'Today' : fmtDay(day)} · {list.length} {list.length === 1 ? 'case' : 'cases'} across {theatres.length} {theatres.length === 1 ? 'theatre' : 'theatres'}</p>
        </div>
        <div className="head-actions">
          <div className="daynav" role="group" aria-label="Choose day">
            <button className="icon-btn" onClick={() => setDay(addDays(day, -1))} aria-label="Previous day"><Icon name="arrowLeft" size={18} /></button>
            <input type="date" className="input date" value={day} onChange={(e) => setDay(e.target.value || todayIso())} aria-label="Day" />
            <button className="icon-btn" onClick={() => setDay(addDays(day, 1))} aria-label="Next day"><Icon name="arrowRight" size={18} /></button>
          </div>
          <Button variant="primary" icon="plus" onClick={() => setAdding(true)}>New case</Button>
        </div>
      </div>

      {list.length > 0 && (
        <div className="stat-row">
          <Stat label="Scheduled today" value={list.length} />
          <Stat label="Ready" value={ready} tone="ok" />
          <Stat label="At risk" value={atRisk} tone={atRisk > 0 ? 'alert' : undefined} />
        </div>
      )}

      {cases.isLoading ? (
        <div className="board">
          {[0, 1, 2].map((i) => <Skeleton key={i} h={92} />)}
        </div>
      ) : cases.isError ? (
        <ErrorState error={cases.error} retry={() => cases.refetch()} />
      ) : list.length === 0 ? (
        <EmptyState
          icon="calendar"
          title={isToday ? 'No cases scheduled today' : `No cases on ${fmtDay(day)}`}
          body="Schedule a case to start paging the team and tracking readiness."
          action={<Button variant="primary" icon="plus" onClick={() => setAdding(true)}>New case</Button>}
        />
      ) : (
        theatres.map(([theatre, rows]) => (
          <section key={theatre} className="theatre-group">
            <div className="theatre-head">
              <Icon name="theatre" size={16} />
              <h2>{theatre}</h2>
              <span className="muted">{rows.length} {rows.length === 1 ? 'case' : 'cases'}</span>
            </div>
            <div className="board">
              {rows.map((c) => (
                <Link key={c.caseId} to={`/cases/${c.caseId}`} className={`case-row ${c.readiness.isReady ? '' : 'flagged'}`}>
                  <div className="case-time">
                    <b>{fmtTime(c.scheduledAt)}</b>
                    {c.durationMins && <span>{c.durationMins} min</span>}
                  </div>
                  <div className="case-main">
                    <b>{c.procedure}</b>
                    <span className="muted">{c.surgeonName}{c.patientName ? ` · ${c.patientName}` : ''}</span>
                    {!c.readiness.isReady && c.readiness.outstanding.length > 0 && (
                      <span className="case-outstanding">
                        <Icon name="alert" size={13} />
                        {c.readiness.outstanding.slice(0, 2).join(' · ')}
                        {c.readiness.outstanding.length > 2 && ` +${c.readiness.outstanding.length - 2}`}
                      </span>
                    )}
                  </div>
                  <div className="case-end">
                    <ReadinessPill readiness={c.readiness} />
                    <Icon name="arrowRight" size={18} />
                  </div>
                </Link>
              ))}
            </div>
          </section>
        ))
      )}

      <NewCaseDialog day={day} open={adding} onClose={() => setAdding(false)} />
    </div>
  );
}
