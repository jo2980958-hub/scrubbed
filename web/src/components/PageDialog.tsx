import { useState, type FormEvent } from 'react';
import { useSendPage } from '../api/hooks';
import { Button, Dialog, Field, useToast } from './ui';

export default function PageDialog({ caseId, open, onClose }: { caseId: string; open: boolean; onClose: () => void }) {
  const send = useSendPage(caseId);
  const toast = useToast();
  const [body, setBody] = useState('');
  const [urgent, setUrgent] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await send.mutateAsync({ body: body.trim(), urgent });
      toast(urgent ? 'Urgent page sent to the team.' : 'Page sent to the team.');
      setBody('');
      setUrgent(false);
      onClose();
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not send the page.', 'err');
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Page the team">
      <form onSubmit={submit} className="form-grid">
        <Field label="Message" htmlFor="pg-body" full hint="Sent to each team member individually. Everyone is asked to acknowledge with a tap.">
          <textarea id="pg-body" className="input" rows={4} value={body} onChange={(e) => setBody(e.target.value)} placeholder="e.g. Start pushed to 14:30. Please acknowledge." required autoFocus />
        </Field>
        <label className="check-inline">
          <input type="checkbox" checked={urgent} onChange={(e) => setUrgent(e.target.checked)} />
          <span>Mark urgent to add a voice call for anyone who has not acknowledged within the window.</span>
        </label>
        <div className="dlg-actions">
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" icon="send" loading={send.isPending} disabled={!body.trim()}>
            Send page
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
