import { useMemo } from 'react';
import { NavLink, Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useCases, useFollowups, useMe } from '../api/hooks';
import { todayIso } from '../lib/dates';
import { Icon, LogoMark, type IconName } from './icons';
import { ErrorState, Skeleton } from './ui';

const NAV: { to: string; label: string; short: string; icon: IconName; end: boolean }[] = [
  { to: '/', label: 'Case board', short: 'Board', icon: 'board', end: true },
  { to: '/followups', label: 'Follow-up queue', short: 'Follow-up', icon: 'followups', end: true },
  { to: '/staff', label: 'Staff', short: 'Staff', icon: 'staff', end: true },
];

function initials(name: string) {
  return name
    .replace(/^(Mr|Ms|Mrs|Dr|Prof)\.?\s+/i, '')
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('');
}

export default function Shell() {
  const auth = useAuth();
  const me = useMe();
  const today = todayIso();
  const cases = useCases(today);
  const followups = useFollowups();

  const atRisk = useMemo(() => (cases.data ?? []).filter((c) => !c.readiness.isReady).length, [cases.data]);
  const needFollowup = useMemo(
    () => (followups.data ?? []).filter((f) => f.status === 'overdue' || f.status === 'escalated' || f.status === 'due').length,
    [followups.data],
  );

  if (!auth.signedIn) return <Navigate to="/login" replace />;

  if (me.isLoading) {
    return (
      <div className="page" style={{ maxWidth: 560, paddingTop: 80 }}>
        <Skeleton h={34} w="60%" />
        <div style={{ height: 16 }} />
        <Skeleton h={120} />
      </div>
    );
  }
  if (me.isError) {
    return (
      <div className="page" style={{ maxWidth: 560, paddingTop: 80 }}>
        <ErrorState error={me.error} retry={() => me.refetch()} />
      </div>
    );
  }

  const staff = me.data!;
  const badge = (to: string) => (to === '/' ? atRisk : to === '/followups' ? needFollowup : 0);

  return (
    <div className="shell">
      <a className="skip" href="#main">Skip to content</a>
      <aside className="sidebar" aria-label="Primary">
        <div className="brand">
          <LogoMark />
          <span>Scrubbed</span>
        </div>
        <nav className="nav" aria-label="Main">
          {NAV.map((n) => {
            const count = badge(n.to);
            return (
              <NavLink key={n.to} to={n.to} end={n.end}>
                <Icon name={n.icon} size={19} />
                <span>{n.label}</span>
                {count > 0 && <span className="count" aria-label={`${count} need attention`}>{count}</span>}
              </NavLink>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <div className="hospital">
            <Icon name="theatre" size={16} />
            <span>{staff.hospitalId}</span>
          </div>
          <div className="who">
            <div className="avatar" aria-hidden="true">{initials(staff.name)}</div>
            <div className="who-text">
              <b>{staff.name}</b>
              <span>{staff.role}</span>
            </div>
            <button className="icon-btn" onClick={auth.signOut} aria-label="Sign out" title="Sign out">
              <Icon name="logout" size={18} />
            </button>
          </div>
        </div>
      </aside>

      <div className="main">
        <header className="mobilebar">
          <div className="brand">
            <LogoMark size={26} />
            <span>Scrubbed</span>
          </div>
          <button className="icon-btn" onClick={auth.signOut} aria-label="Sign out">
            <Icon name="logout" size={18} />
          </button>
        </header>
        <main id="main" tabIndex={-1}>
          <Outlet />
        </main>
      </div>

      <nav className="tabbar" aria-label="Main">
        {NAV.map((n) => {
          const count = badge(n.to);
          return (
            <NavLink key={n.to} to={n.to} end={n.end}>
              <span className="tab-ico">
                <Icon name={n.icon} size={20} />
                {count > 0 && <span className="tab-dot" aria-hidden="true" />}
              </span>
              {n.short}
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
}
