import { useForms } from '../../api/hooks';
import { fmtDateTime } from '../../lib/dates';
import { Card, EmptyState, ErrorState, FormChip, SectionTitle, Skeleton } from '../ui';
import { Icon } from '../icons';

export default function CaseForms({ caseId }: { caseId: string }) {
  const forms = useForms(caseId);

  if (forms.isLoading) return <Card><Skeleton h={30} w="40%" /><div style={{ height: 14 }} /><Skeleton h={120} /></Card>;
  if (forms.isError) return <ErrorState error={forms.error} retry={() => forms.refetch()} />;
  const list = forms.data ?? [];
  if (list.length === 0) {
    return <Card><EmptyState icon="forms" title="No forms on this case" body="When a team member does not respond to a page, the agent sends them a short form. Completed forms are filed here against the case." /></Card>;
  }

  return (
    <Card>
      <SectionTitle title="Uploaded forms" hint="Handovers, sign-offs and count records filed against this case" />
      <ul className="forms-list">
        {list.map((f) => (
          <li key={f.formId}>
            <span className="form-ico" aria-hidden="true"><Icon name="forms" size={18} /></span>
            <div className="form-main">
              <b>{f.kind}</b>
              <span className="muted">
                {f.staffName}{f.role ? ` · ${f.role}` : ''}
                {f.uploadedAt ? ` · uploaded ${fmtDateTime(f.uploadedAt)}` : f.requestedAt ? ` · requested ${fmtDateTime(f.requestedAt)}` : ''}
              </span>
            </div>
            <div className="form-end">
              <FormChip status={f.status} />
              {f.url ? (
                <a className="btn sm" href={f.url} target="_blank" rel="noreferrer">
                  <Icon name="external" size={15} />
                  Open
                </a>
              ) : (
                <span className="muted awaiting">Awaiting upload</span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
