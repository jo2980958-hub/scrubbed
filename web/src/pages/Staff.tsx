import { useState, type FormEvent } from 'react';
import { useAddStaff, useStaff } from '../api/hooks';
import { Button, Card, Dialog, EmptyState, ErrorState, Field, SectionTitle, Skeleton, useToast, usePageTitle } from '../components/ui';
import { Icon } from '../components/icons';

const ROLES = [
  'Consultant Surgeon', 'Registrar', 'Anaesthetist', 'Scrub Nurse', 'Circulating Nurse', 'ODP', 'Charge Nurse', 'Coordinator',
];

function initials(name: string) {
  return name
    .replace(/^(Mr|Ms|Mrs|Dr|Prof)\.?\s+/i, '')
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('');
}

function AddStaffDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const add = useAddStaff();
  const toast = useToast();
  const [name, setName] = useState('');
  const [role, setRole] = useState(ROLES[0]);
  const [email, setEmail] = useState('');
  const [whatsappNumber, setNumber] = useState('');

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await add.mutateAsync({ name: name.trim(), role, email: email.trim(), whatsappNumber: whatsappNumber.trim() });
      toast(`${name} added. They can now link their number by one-time code.`);
      setName(''); setEmail(''); setNumber('');
      onClose();
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not add staff member.', 'err');
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Add a staff member">
      <form onSubmit={submit} className="form-grid">
        <Field label="Full name" htmlFor="st-name" full>
          <input id="st-name" className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Dr Hannah Beck" required autoFocus />
        </Field>
        <Field label="Role" htmlFor="st-role">
          <select id="st-role" className="input" value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLES.map((r) => <option key={r}>{r}</option>)}
          </select>
        </Field>
        <Field label="WhatsApp number" htmlFor="st-num">
          <input id="st-num" className="input" value={whatsappNumber} onChange={(e) => setNumber(e.target.value)} placeholder="+44 7700 900000" required />
        </Field>
        <Field label="Work email" htmlFor="st-email" full hint="The one-time login code is sent here.">
          <input id="st-email" className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@hospital.nhs.uk" required />
        </Field>
        <div className="dlg-actions">
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" loading={add.isPending} disabled={!name || !email || !whatsappNumber}>Add staff member</Button>
        </div>
      </form>
    </Dialog>
  );
}

export default function Staff() {
  usePageTitle('Staff');
  const q = useStaff();
  const [adding, setAdding] = useState(false);
  const list = q.data ?? [];

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Staff</h1>
          <p className="muted">Staff are added here, then link their WhatsApp number by one-time code. No self-sign-up.</p>
        </div>
        <Button variant="primary" icon="plus" onClick={() => setAdding(true)}>Add staff</Button>
      </div>

      {q.isLoading ? (
        <Card><Skeleton h={30} w="40%" /><div style={{ height: 14 }} /><Skeleton h={160} /></Card>
      ) : q.isError ? (
        <ErrorState error={q.error} retry={() => q.refetch()} />
      ) : list.length === 0 ? (
        <Card><EmptyState icon="staff" title="No staff yet" body="Add the coordinator, surgeons and theatre staff so they can be paged." action={<Button variant="primary" icon="plus" onClick={() => setAdding(true)}>Add staff</Button>} /></Card>
      ) : (
        <Card>
          <SectionTitle title="Roster" hint={`${list.length} people · ${list.filter((s) => s.linked).length} linked to WhatsApp`} />
          <ul className="staff-list">
            {list.map((s) => (
              <li key={s.staffId}>
                <span className="avatar sm" aria-hidden="true">{initials(s.name)}</span>
                <div className="staff-main">
                  <b>{s.name}</b>
                  <span className="muted">{s.role}</span>
                </div>
                <div className="staff-contact muted">
                  <span>{s.whatsappNumber}</span>
                  <span>{s.email}</span>
                </div>
                <span className={`chip ${s.linked ? 'ok' : 'muted'}`}>
                  {s.linked ? <><Icon name="check" size={13} />Linked</> : 'Not linked'}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <AddStaffDialog open={adding} onClose={() => setAdding(false)} />
    </div>
  );
}
