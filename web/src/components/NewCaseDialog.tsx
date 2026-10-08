import { useState, type FormEvent } from 'react';
import { useCreateCase } from '../api/hooks';
import { useStaff } from '../api/hooks';
import { Button, Dialog, Field, useToast } from './ui';

export default function NewCaseDialog({ day, open, onClose }: { day: string; open: boolean; onClose: () => void }) {
  const create = useCreateCase(day);
  const staff = useStaff();
  const toast = useToast();
  const [procedure, setProcedure] = useState('');
  const [theatre, setTheatre] = useState('Theatre 2');
  const [time, setTime] = useState('15:30');
  const [surgeon, setSurgeon] = useState('');
  const [patient, setPatient] = useState('');

  const surgeons = (staff.data ?? []).filter((s) => s.role === 'Consultant Surgeon');

  async function submit(e: FormEvent) {
    e.preventDefault();
    const scheduledAt = new Date(`${day}T${time}:00`).toISOString();
    try {
      await create.mutateAsync({
        procedure: procedure.trim(),
        theatre,
        scheduledAt,
        surgeonName: surgeon || surgeons[0]?.name || 'Unassigned',
        patientName: patient.trim(),
      });
      toast('Case added to the board.');
      setProcedure('');
      setPatient('');
      onClose();
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not add the case.', 'err');
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Schedule a case">
      <form onSubmit={submit} className="form-grid">
        <Field label="Procedure" htmlFor="nc-proc" full>
          <input id="nc-proc" className="input" value={procedure} onChange={(e) => setProcedure(e.target.value)} placeholder="e.g. Laparoscopic cholecystectomy" required autoFocus />
        </Field>
        <Field label="Patient name" htmlFor="nc-patient" full>
          <input id="nc-patient" className="input" value={patient} onChange={(e) => setPatient(e.target.value)} placeholder="Full name" required />
        </Field>
        <Field label="Theatre" htmlFor="nc-theatre">
          <select id="nc-theatre" className="input" value={theatre} onChange={(e) => setTheatre(e.target.value)}>
            <option>Theatre 2</option>
            <option>Theatre 5</option>
            <option>Day surgery</option>
          </select>
        </Field>
        <Field label="Start time" htmlFor="nc-time">
          <input id="nc-time" className="input" type="time" value={time} onChange={(e) => setTime(e.target.value)} required />
        </Field>
        <Field label="Surgeon" htmlFor="nc-surgeon" full>
          <select id="nc-surgeon" className="input" value={surgeon} onChange={(e) => setSurgeon(e.target.value)}>
            {surgeons.length === 0 && <option value="">Unassigned</option>}
            {surgeons.map((s) => (
              <option key={s.staffId} value={s.name}>{s.name}</option>
            ))}
          </select>
        </Field>
        <div className="dlg-actions">
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" loading={create.isPending} disabled={!procedure || !patient}>
            Add to board
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
