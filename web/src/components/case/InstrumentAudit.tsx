import { fmtTime } from '../../lib/dates';
import { Card, EmptyState, SectionTitle } from '../ui';
import { Icon } from '../icons';
import type { Tray, TrayLine } from '../../api/types';

const LOW_CONFIDENCE = 0.8;

function Catalogue({ title, at, lines }: { title: string; at?: string | null; lines: TrayLine[] }) {
  return (
    <div className="catalogue">
      <div className="catalogue-head">
        <b>{title}</b>
        {at && <span className="muted">{fmtTime(at)}</span>}
      </div>
      {lines.length === 0 ? (
        <p className="muted catalogue-empty">Not sent yet.</p>
      ) : (
        <ul className="catalogue-list">
          {lines.map((l) => (
            <li key={l.item}>
              <span className="cat-item">{l.item}</span>
              <span className="cat-count num">{l.count}</span>
              <span className={`cat-conf ${l.confidence < LOW_CONFIDENCE ? 'low' : ''}`}>
                {l.confidence < LOW_CONFIDENCE ? 'please verify' : `${Math.round(l.confidence * 100)}%`}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function InstrumentAudit({ tray }: { tray: Tray | null }) {
  if (!tray || (tray.before.length === 0 && tray.after.length === 0)) {
    return (
      <Card>
        <SectionTitle title="Instrument second-count" hint="A photo-based second check. The manual WHO count remains the authority." />
        <EmptyState icon="tray" title="No tray photos yet" body="The scrub nurse sends a photo of the laid-out tray before the case, and a second after closing. Scrubbed compares them and flags anything unaccounted for." />
      </Card>
    );
  }

  const flagged = tray.diff.filter((d) => d.flagged);
  const awaitingAfter = tray.after.length === 0;

  return (
    <Card className="audit">
      <SectionTitle
        title="Instrument second-count"
        hint="A photo-based second check. It flags discrepancies for a human; the manual WHO count remains the authority."
      />

      {flagged.length > 0 ? (
        <div className="banner alert" role="alert">
          <Icon name="alert" size={18} />
          <div>
            <b>{flagged.length === 1 ? 'One item flagged as unaccounted for' : `${flagged.length} items flagged as unaccounted for`}</b>
            <div>
              {flagged.map((d) => `${d.item} (${d.before} before, ${d.after} after)`).join('; ')}. Repeat the manual count now.
            </div>
          </div>
        </div>
      ) : awaitingAfter ? (
        <div className="banner info">
          <Icon name="clock" size={18} />
          <div><b>Before photo received.</b><div>Waiting for the after photo once the case closes.</div></div>
        </div>
      ) : (
        <div className="banner ok">
          <Icon name="checkCircle" size={18} />
          <div><b>No discrepancy from the second-count.</b><div>Every catalogued item seen before was seen after. The manual count still applies.</div></div>
        </div>
      )}

      <div className="photos">
        {tray.beforePhotoUrl && (
          <figure>
            <img src={tray.beforePhotoUrl} alt="Instrument tray before the case" loading="lazy" />
            <figcaption>Before {tray.beforeAt && `· ${fmtTime(tray.beforeAt)}`}</figcaption>
          </figure>
        )}
        {tray.afterPhotoUrl ? (
          <figure>
            <img src={tray.afterPhotoUrl} alt="Instrument tray after the case" loading="lazy" />
            <figcaption>After {tray.afterAt && `· ${fmtTime(tray.afterAt)}`}</figcaption>
          </figure>
        ) : (
          <figure className="photo-empty">
            <div className="photo-ph" aria-hidden="true"><Icon name="tray" size={28} /></div>
            <figcaption>After · awaited</figcaption>
          </figure>
        )}
      </div>

      <div className="catalogues">
        <Catalogue title="Catalogue before" at={tray.beforeAt} lines={tray.before} />
        <Catalogue title="Catalogue after" at={tray.afterAt} lines={tray.after} />
      </div>

      {tray.diff.length > 0 && (
        <table className="diff-table">
          <thead>
            <tr><th>Instrument</th><th className="num">Before</th><th className="num">After</th><th className="num">Diff</th><th>Result</th></tr>
          </thead>
          <tbody>
            {tray.diff.map((d) => (
              <tr key={d.item} className={d.flagged ? 'flagged' : ''}>
                <td>{d.item}</td>
                <td className="num">{d.before}</td>
                <td className="num">{d.after}</td>
                <td className="num">{d.delta > 0 ? `+${d.delta}` : d.delta}</td>
                <td>
                  {d.flagged ? (
                    <span className="chip alert"><Icon name="alert" size={13} />Unaccounted</span>
                  ) : (
                    <span className="chip ok">Accounted for</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tray.acknowledgedBy && (
        <p className="audit-ack muted">
          <Icon name="check" size={14} />
          Acknowledged by {tray.acknowledgedBy}{tray.acknowledgedAt && ` at ${fmtTime(tray.acknowledgedAt)}`}.
        </p>
      )}
    </Card>
  );
}
