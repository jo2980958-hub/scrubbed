import { todayIso } from '../lib/dates';
import type {
  CaseDetail,
  CaseSummary,
  Checklist,
  ChecklistItem,
  Me,
  Patient,
  Readiness,
  ReadinessItem,
  Staff,
  Tray,
  TeamMember,
} from './types';

/* ------------------------------------------------------------------ clock */

const DAY = 86_400_000;
export const today = todayIso();
export const atToday = (hhmm: string): string => {
  const [h, m] = hhmm.split(':').map(Number);
  const d = new Date(`${today}T00:00:00`);
  d.setHours(h, m, 0, 0);
  return d.toISOString();
};
export const minsAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString();
export const hrsAgo = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString();
export const daysFromNow = (n: number) => new Date(Date.now() + n * DAY).toISOString();

export const latency = <T,>(value: T, ms = 320): Promise<T> =>
  new Promise((resolve) => setTimeout(() => resolve(value), ms));

/* ------------------------------------------------------------------ staff */

export const me: Me = {
  name: 'Priya Nair',
  role: 'Coordinator',
  hospitalId: 'St Aldate’s General',
  email: 'rota@st-aldates.nhs.uk',
};

export const staff: Staff[] = [
  { staffId: 'stf_priya', name: 'Priya Nair', role: 'Coordinator', email: 'rota@st-aldates.nhs.uk', whatsappNumber: '+44 7700 900100', linked: true },
  { staffId: 'stf_adeyemi', name: 'Mr David Adeyemi', role: 'Consultant Surgeon', email: 'd.adeyemi@st-aldates.nhs.uk', whatsappNumber: '+44 7700 900111', linked: true },
  { staffId: 'stf_okafor', name: 'Ms Chioma Okafor', role: 'Consultant Surgeon', email: 'c.okafor@st-aldates.nhs.uk', whatsappNumber: '+44 7700 900112', linked: true },
  { staffId: 'stf_whitfield', name: 'Dr Sam Whitfield', role: 'Registrar', email: 's.whitfield@st-aldates.nhs.uk', whatsappNumber: '+44 7700 900121', linked: true },
  { staffId: 'stf_beck', name: 'Dr Hannah Beck', role: 'Anaesthetist', email: 'h.beck@st-aldates.nhs.uk', whatsappNumber: '+44 7700 900131', linked: true },
  { staffId: 'stf_rahimi', name: 'Dr Omar Rahimi', role: 'Anaesthetist', email: 'o.rahimi@st-aldates.nhs.uk', whatsappNumber: '+44 7700 900132', linked: true },
  { staffId: 'stf_mensah', name: 'Lucy Mensah', role: 'Scrub Nurse', email: 'l.mensah@st-aldates.nhs.uk', whatsappNumber: '+44 7700 900141', linked: true },
  { staffId: 'stf_balogun', name: 'Tunde Balogun', role: 'Scrub Nurse', email: 't.balogun@st-aldates.nhs.uk', whatsappNumber: '+44 7700 900142', linked: true },
  { staffId: 'stf_appiah', name: 'Grace Appiah', role: 'Circulating Nurse', email: 'g.appiah@st-aldates.nhs.uk', whatsappNumber: '+44 7700 900151', linked: true },
  { staffId: 'stf_deller', name: 'Mark Deller', role: 'ODP', email: 'm.deller@st-aldates.nhs.uk', whatsappNumber: '+44 7700 900161', linked: true },
  { staffId: 'stf_osei', name: 'Rita Osei', role: 'Charge Nurse', email: 'r.osei@st-aldates.nhs.uk', whatsappNumber: '+44 7700 900171', linked: false },
];

export const member = (id: string): TeamMember => {
  const s = staff.find((x) => x.staffId === id)!;
  return { staffId: s.staffId, name: s.name, role: s.role };
};

export const theatre2Team = ['stf_adeyemi', 'stf_whitfield', 'stf_beck', 'stf_mensah', 'stf_appiah', 'stf_deller'].map(member);
export const theatre5Team = ['stf_okafor', 'stf_rahimi', 'stf_balogun', 'stf_appiah', 'stf_deller'].map(member);

/* -------------------------------------------------------------- checklist */

interface Tmpl {
  key: string;
  label: string;
  phase: ChecklistItem['phase'];
}
const CHECKLIST_TMPL: Tmpl[] = [
  { key: 'si_identity', label: 'Patient identity, site and procedure confirmed', phase: 'sign-in' },
  { key: 'si_consent', label: 'Consent form signed and in the notes', phase: 'sign-in' },
  { key: 'si_site', label: 'Surgical site marked', phase: 'sign-in' },
  { key: 'si_anaesthesia', label: 'Anaesthesia safety check complete', phase: 'sign-in' },
  { key: 'si_allergy', label: 'Known allergies checked', phase: 'sign-in' },
  { key: 'si_airway', label: 'Airway or aspiration risk assessed', phase: 'sign-in' },
  { key: 'to_team', label: 'Team introduced by name and role', phase: 'time-out' },
  { key: 'to_confirm', label: 'Surgeon, anaesthetist and nurse confirm patient, site and procedure', phase: 'time-out' },
  { key: 'to_antibiotic', label: 'Antibiotic prophylaxis given in the last 60 minutes', phase: 'time-out' },
  { key: 'to_imaging', label: 'Essential imaging displayed', phase: 'time-out' },
  { key: 'so_count', label: 'Instrument, swab and needle counts correct', phase: 'sign-out' },
  { key: 'so_specimen', label: 'Specimen labelled', phase: 'sign-out' },
  { key: 'so_equipment', label: 'Equipment problems recorded', phase: 'sign-out' },
];

export function checklist(done: string[], by?: string, at?: string): Checklist {
  const set = new Set(done);
  return {
    items: CHECKLIST_TMPL.map((t) => ({
      key: t.key,
      label: t.label,
      phase: t.phase,
      done: set.has(t.key),
      confirmedBy: set.has(t.key) ? by : undefined,
      confirmedAt: set.has(t.key) ? at : undefined,
    })),
  };
}

export const ALL_DONE = CHECKLIST_TMPL.map((t) => t.key);
export const SIGNIN_TIMEOUT = CHECKLIST_TMPL.filter((t) => t.phase !== 'sign-out').map((t) => t.key);

/* -------------------------------------------------------------- readiness */

export function readiness(
  score: number,
  risk: Readiness['risk'],
  items: ReadinessItem[],
): Readiness {
  const outstanding = items.filter((i) => i.state !== 'done').map((i) => i.label);
  return { score, isReady: score >= 90 && risk === 'none', risk, outstanding, items };
}

const readyItems: ReadinessItem[] = [
  { key: 'rd_consent', label: 'Consent signed', state: 'done' },
  { key: 'rd_fasting', label: 'Fasting confirmed', state: 'done', detail: 'Nil by mouth from 02:00' },
  { key: 'rd_bloods', label: 'Pre-op bloods and group & save', state: 'done' },
  { key: 'rd_instructions', label: 'Pre-op instructions acknowledged', state: 'done' },
  { key: 'rd_balance', label: 'Patient balance cleared', state: 'done' },
  { key: 'rd_transport', label: 'Arrival and transport confirmed', state: 'done' },
];

const atRiskItems: ReadinessItem[] = [
  { key: 'rd_consent', label: 'Consent not signed', state: 'blocked', detail: 'Surgeon to obtain written consent before 13:00' },
  { key: 'rd_fasting', label: 'Fasting not confirmed', state: 'pending', detail: 'Patient has not confirmed nil by mouth' },
  { key: 'rd_bloods', label: 'Pre-op bloods and group & save', state: 'done' },
  { key: 'rd_instructions', label: 'Pre-op instructions acknowledged', state: 'done' },
  { key: 'rd_balance', label: 'Balance £240.00 outstanding', state: 'blocked', detail: 'Self-funded excess not yet cleared' },
  { key: 'rd_transport', label: 'Arrival and transport confirmed', state: 'done' },
];

const bloodsPendingItems: ReadinessItem[] = [
  { key: 'rd_consent', label: 'Consent signed', state: 'done' },
  { key: 'rd_fasting', label: 'Fasting confirmed', state: 'done', detail: 'Nil by mouth from 06:00' },
  { key: 'rd_bloods', label: 'Pre-op bloods pending', state: 'pending', detail: 'Phlebotomy booked for 11:30' },
  { key: 'rd_instructions', label: 'Pre-op instructions acknowledged', state: 'done' },
  { key: 'rd_balance', label: 'Patient balance cleared', state: 'done' },
  { key: 'rd_transport', label: 'Arrival and transport confirmed', state: 'done' },
];

/* ------------------------------------------------------------------ cases */

export interface Seed {
  summary: CaseSummary;
  stage: CaseDetail['case']['stage'];
  team: TeamMember[];
  patient: Patient;
  checklist: Checklist;
  tray: Tray | null;
  anaesthetic?: string;
  notes?: string;
}

export const seeds: Record<string, Seed> = {
  case_0801: {
    summary: {
      caseId: 'case_0801',
      procedure: 'Laparoscopic cholecystectomy',
      procedureCode: 'J18.3',
      theatre: 'Theatre 2',
      scheduledAt: atToday('08:30'),
      durationMins: 75,
      surgeonName: 'Mr David Adeyemi',
      patientName: 'Grace Bennett',
      readiness: readiness(100, 'none', readyItems),
    },
    stage: 'complete',
    team: theatre2Team,
    patient: { name: 'Grace Bennett', balancePence: 0, dateOfBirth: '1968-04-12', mrn: 'MRN 40921', phone: '+44 7700 900310' },
    checklist: checklist(ALL_DONE, 'Lucy Mensah', atToday('08:25')),
    anaesthetic: 'General',
    tray: {
      beforePhotoUrl: '/tray-before.svg',
      afterPhotoUrl: '/tray-before.svg',
      beforeAt: atToday('08:10'),
      afterAt: atToday('09:40'),
      acknowledgedBy: 'Lucy Mensah',
      acknowledgedAt: atToday('09:42'),
      before: [
        { item: 'Artery forceps', count: 6, confidence: 0.94 },
        { item: 'Scalpel handle', count: 2, confidence: 0.97 },
        { item: 'Mayo scissors', count: 1, confidence: 0.92 },
        { item: 'Swab', count: 10, confidence: 0.88 },
      ],
      after: [
        { item: 'Artery forceps', count: 6, confidence: 0.91 },
        { item: 'Scalpel handle', count: 2, confidence: 0.96 },
        { item: 'Mayo scissors', count: 1, confidence: 0.9 },
        { item: 'Swab', count: 10, confidence: 0.86 },
      ],
      diff: [
        { item: 'Artery forceps', before: 6, after: 6, delta: 0, flagged: false },
        { item: 'Scalpel handle', before: 2, after: 2, delta: 0, flagged: false },
        { item: 'Mayo scissors', before: 1, after: 1, delta: 0, flagged: false },
        { item: 'Swab', before: 10, after: 10, delta: 0, flagged: false },
      ],
    },
  },

  case_1100: {
    summary: {
      caseId: 'case_1100',
      procedure: 'Right inguinal hernia repair',
      procedureCode: 'T20.1',
      theatre: 'Theatre 2',
      scheduledAt: atToday('11:00'),
      durationMins: 60,
      surgeonName: 'Mr David Adeyemi',
      patientName: 'Harold Kemp',
      readiness: readiness(95, 'none', readyItems),
    },
    stage: 'in-theatre',
    team: theatre2Team,
    patient: { name: 'Harold Kemp', balancePence: 0, dateOfBirth: '1955-11-02', mrn: 'MRN 41188', phone: '+44 7700 900311' },
    checklist: checklist(SIGNIN_TIMEOUT, 'Lucy Mensah', atToday('11:05')),
    anaesthetic: 'General',
    tray: {
      beforePhotoUrl: '/tray-before.svg',
      afterPhotoUrl: null,
      beforeAt: atToday('10:50'),
      afterAt: null,
      before: [
        { item: 'Artery forceps', count: 6, confidence: 0.93 },
        { item: 'Scalpel handle', count: 2, confidence: 0.96 },
        { item: 'Mayo scissors', count: 1, confidence: 0.9 },
        { item: 'Needle holder', count: 2, confidence: 0.89 },
        { item: 'Swab', count: 10, confidence: 0.87 },
      ],
      after: [],
      diff: [],
    },
  },

  case_1400: {
    summary: {
      caseId: 'case_1400',
      procedure: 'Laparoscopic cholecystectomy',
      procedureCode: 'J18.3',
      theatre: 'Theatre 2',
      scheduledAt: atToday('14:00'),
      durationMins: 90,
      surgeonName: 'Mr David Adeyemi',
      patientName: 'Idris Mahama',
      readiness: readiness(55, 'high', atRiskItems),
    },
    stage: 'scheduled',
    team: theatre2Team,
    patient: { name: 'Idris Mahama', balancePence: 24000, dateOfBirth: '1979-07-21', mrn: 'MRN 41204', phone: '+44 7700 900312' },
    checklist: checklist([], undefined, undefined),
    anaesthetic: 'General',
    notes: 'Self-funded. Consent outstanding — surgeon to see on the ward before 13:00.',
    tray: null,
  },

  case_0900: {
    summary: {
      caseId: 'case_0900',
      procedure: 'Total knee replacement',
      procedureCode: 'W40.1',
      theatre: 'Theatre 5',
      scheduledAt: atToday('09:00'),
      durationMins: 120,
      surgeonName: 'Ms Chioma Okafor',
      patientName: 'Margaret Wiley',
      readiness: readiness(100, 'none', readyItems),
    },
    stage: 'complete',
    team: theatre5Team,
    patient: { name: 'Margaret Wiley', balancePence: 0, dateOfBirth: '1951-01-30', mrn: 'MRN 39877', phone: '+44 7700 900313' },
    checklist: checklist(ALL_DONE, 'Tunde Balogun', atToday('09:05')),
    anaesthetic: 'Spinal',
    notes: 'Instrument second-count flagged one artery forceps unaccounted for. Manual WHO count repeated; see audit.',
    tray: {
      beforePhotoUrl: '/tray-before.svg',
      afterPhotoUrl: '/tray-after.svg',
      beforeAt: atToday('08:45'),
      afterAt: atToday('11:20'),
      acknowledgedBy: 'Tunde Balogun',
      acknowledgedAt: atToday('11:26'),
      before: [
        { item: 'Artery forceps', count: 6, confidence: 0.93 },
        { item: 'Scalpel handle', count: 2, confidence: 0.97 },
        { item: 'Mayo scissors', count: 1, confidence: 0.92 },
        { item: 'Retractor', count: 2, confidence: 0.9 },
        { item: 'Needle holder', count: 1, confidence: 0.84 },
        { item: 'Swab', count: 10, confidence: 0.82 },
      ],
      after: [
        { item: 'Artery forceps', count: 5, confidence: 0.9 },
        { item: 'Scalpel handle', count: 2, confidence: 0.96 },
        { item: 'Mayo scissors', count: 1, confidence: 0.91 },
        { item: 'Retractor', count: 2, confidence: 0.89 },
        { item: 'Needle holder', count: 1, confidence: 0.79 },
        { item: 'Swab', count: 10, confidence: 0.8 },
      ],
      diff: [
        { item: 'Artery forceps', before: 6, after: 5, delta: -1, flagged: true },
        { item: 'Scalpel handle', before: 2, after: 2, delta: 0, flagged: false },
        { item: 'Mayo scissors', before: 1, after: 1, delta: 0, flagged: false },
        { item: 'Retractor', before: 2, after: 2, delta: 0, flagged: false },
        { item: 'Needle holder', before: 1, after: 1, delta: 0, flagged: false },
        { item: 'Swab', before: 10, after: 10, delta: 0, flagged: false },
      ],
    },
  },

  case_1330: {
    summary: {
      caseId: 'case_1330',
      procedure: 'Knee arthroscopy',
      procedureCode: 'W82.1',
      theatre: 'Theatre 5',
      scheduledAt: atToday('13:30'),
      durationMins: 45,
      surgeonName: 'Ms Chioma Okafor',
      patientName: 'Peter Lund',
      readiness: readiness(90, 'low', bloodsPendingItems),
    },
    stage: 'scheduled',
    team: theatre5Team,
    patient: { name: 'Peter Lund', balancePence: 0, dateOfBirth: '1990-09-14', mrn: 'MRN 41250', phone: '+44 7700 900314' },
    checklist: checklist([], undefined, undefined),
    anaesthetic: 'General',
    tray: null,
  },
};

/* ------------------------------------------------------------- mutable set */

/** Hold mutations in memory for the session so create/patch/page feel live. */
export const order = ['case_0801', 'case_0900', 'case_1100', 'case_1330', 'case_1400'];

export function sortByTime(ids: string[]): CaseSummary[] {
  return ids
    .map((id) => seeds[id]?.summary)
    .filter((s): s is CaseSummary => !!s)
    .sort((a, b) => a.scheduledAt.localeCompare(b.scheduledAt));
}
