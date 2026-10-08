import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { DEMO } from '../config';
import { Button, Field } from '../components/ui';
import { Icon, LogoMark } from '../components/icons';

export default function Login() {
  const auth = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [newPw, setNewPw] = useState('');
  const [challenge, setChallenge] = useState<{ username: string; session: string } | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (auth.signedIn) return <Navigate to="/" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      if (challenge) {
        if (newPw.length < 8) throw new Error('Choose a password of at least 8 characters.');
        await auth.finishNewPassword(challenge.username, newPw, challenge.session);
        nav('/', { replace: true });
      } else {
        const r = await auth.signIn(email.trim(), password);
        if (r.kind === 'new_password') setChallenge({ username: r.username, session: r.challengeSession });
        else nav('/', { replace: true });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not sign in.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth">
      <aside className="auth-art">
        <div className="brand brand-light">
          <LogoMark size={34} />
          <span>Scrubbed</span>
        </div>
        <div className="auth-art-body">
          <h2>Every case ready. Nothing missed around it.</h2>
          <p>
            The command centre for the perioperative team: today’s theatres and their readiness, the paging ladder,
            the instrument second-count and post-op follow-up, kept as one record.
          </p>

          <div className="auth-preview" aria-hidden="true">
            <div className="prev-row">
              <div className="prev-time">14:00</div>
              <div className="prev-main">
                <b>Laparoscopic cholecystectomy</b>
                <span>Theatre 2 · Mr Adeyemi</span>
              </div>
              <span className="pill ready-high"><span className="dot" />At risk<span className="pill-score">55</span></span>
            </div>
            <div className="prev-row">
              <div className="prev-time">09:00</div>
              <div className="prev-main">
                <b>Total knee replacement</b>
                <span>Theatre 5 · Ms Okafor</span>
              </div>
              <span className="pill ready-ready"><span className="dot" />Ready<span className="pill-score">100</span></span>
            </div>
            <div className="prev-flag">
              <Icon name="alert" size={15} />
              Second-count flag: 1 artery forceps present before, not seen after.
            </div>
          </div>
        </div>
        <small>Operational support only. Not a medical device. The manual WHO count remains the authority.</small>
      </aside>

      <main className="auth-form-wrap" id="main">
        <form className="auth-form" onSubmit={submit} noValidate>
          <div>
            <h1>{challenge ? 'Choose your password' : 'Sign in'}</h1>
            <p className="muted" style={{ marginTop: 6 }}>
              {challenge
                ? 'This is your first sign-in. Set a password you will remember.'
                : 'Sign in to the coordinator dashboard.'}
            </p>
          </div>

          {error && (
            <div className="banner alert" role="alert">
              <Icon name="alert" size={18} />
              <span>{error}</span>
            </div>
          )}

          {DEMO ? (
            <>
              <Button variant="primary" className="block" onClick={() => { auth.enterDemo(); nav('/', { replace: true }); }}>
                Open the dashboard
                <Icon name="arrowRight" size={16} />
              </Button>
              <p className="auth-foot">St Aldate’s General · theatre list for today.</p>
            </>
          ) : challenge ? (
            <>
              <Field label="New password" htmlFor="newpw" hint="At least 8 characters.">
                <input id="newpw" className="input" type="password" autoComplete="new-password" value={newPw} onChange={(e) => setNewPw(e.target.value)} autoFocus />
              </Field>
              <Button variant="primary" className="block" type="submit" loading={busy}>Set password and continue</Button>
            </>
          ) : (
            <>
              <Field label="Work email" htmlFor="email">
                <input id="email" className="input" type="email" autoComplete="username" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
              </Field>
              <Field label="Password" htmlFor="password">
                <input id="password" className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
              </Field>
              <Button variant="primary" className="block" type="submit" loading={busy} disabled={!email || !password}>Sign in</Button>
              <p className="auth-foot">Protected by Amazon Cognito. Staff are added by an admin, then linked by one-time code.</p>
            </>
          )}
        </form>
      </main>
    </div>
  );
}
