import { todayIso } from '../lib/dates';
import type {
  CaseDetail,
  CasePatch,
  CaseSummary,
  Checklist,
  ChecklistItem,
  Followup,
  FormRecord,
  Me,
  Message,
  NewCaseInput,
  NewStaffInput,
  PageInput,
  PageRecord,
  Patient,
  Readiness,
  ReadinessItem,
  Staff,
  Tray,
  TeamMember,
} from './types';

/* ------------------------------------------------------------------ clock */

const DAY = 86_400_000;
const today = todayIso();
const atToday = (hhmm: string): string => {
  const [h, m] = hhmm.split(':').map(Number);
  const d = new Date(`${today}T00:00:00`);
  d.setHours(h, m, 0, 0);
  return d.toISOString();
};
const minsAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString();
const hrsAgo = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString();
const daysFromNow = (n: number) => new Date(Date.now() + n * DAY).toISOString();

const latency = <T,>(value: T, ms = 320): Promise<T> =>
  new Promise((resolve) => setTimeout(() => resolve(value), ms));

/* ------------------------------------------------------------------ staff */

const me: Me = {
  name: 'Priya Nair',
  role: 'Coordinator',
  hospitalId: 'St Aldate’s General',
  email: 'rota@st-aldates.nhs.uk',
};

const staff: Staff[] = [
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

const member = (id: string): TeamMember => {
  const s = staff.find((x) => x.staffId === id)!;
  return { staffId: s.staffId, name: s.name, role: s.role };
};

const theatre2Team = ['stf_adeyemi', 'stf_whitfield', 'stf_beck', 'stf_mensah', 'stf_appiah', 'stf_deller'].map(member);
const theatre5Team = ['stf_okafor', 'stf_rahimi', 'stf_balogun', 'stf_appiah', 'stf_deller'].map(member);

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

function checklist(done: string[], by?: string, at?: string): Checklist {
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

const ALL_DONE = CHECKLIST_TMPL.map((t) => t.key);
const SIGNIN_TIMEOUT = CHECKLIST_TMPL.filter((t) => t.phase !== 'sign-out').map((t) => t.key);

/* -------------------------------------------------------------- readiness */

function readiness(
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

interface Seed {
  summary: CaseSummary;
  stage: CaseDetail['case']['stage'];
  team: TeamMember[];
  patient: Patient;
  checklist: Checklist;
  tray: Tray | null;
  anaesthetic?: string;
  notes?: string;
}

const seeds: Record<string, Seed> = {
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

/* ------------------------------------------------------------------ paging */

const pagesByCase: Record<string, PageRecord[]> = {
  case_1400: [
    {
      pageId: 'page_1400_a',
      createdAt: minsAgo(44),
      urgent: true,
      body: 'Theatre 2, 14:00 — Lap cholecystectomy, Mr Adeyemi. Case is at risk: consent and balance outstanding. Please acknowledge and confirm you are covering your role.',
      recipients: [
        { staffId: 'stf_adeyemi', name: 'Mr David Adeyemi', role: 'Consultant Surgeon', status: 'acknowledged', sentAt: minsAgo(44), deliveredAt: minsAgo(44), readAt: minsAgo(42), acknowledgedAt: minsAgo(40), escalated: false },
        { staffId: 'stf_beck', name: 'Dr Hannah Beck', role: 'Anaesthetist', status: 'acknowledged', sentAt: minsAgo(44), deliveredAt: minsAgo(43), readAt: minsAgo(41), acknowledgedAt: minsAgo(38), escalated: false },
        { staffId: 'stf_mensah', name: 'Lucy Mensah', role: 'Scrub Nurse', status: 'acknowledged', sentAt: minsAgo(44), deliveredAt: minsAgo(44), readAt: minsAgo(40), acknowledgedAt: minsAgo(37), escalated: false },
        { staffId: 'stf_whitfield', name: 'Dr Sam Whitfield', role: 'Registrar', status: 'read', sentAt: minsAgo(44), deliveredAt: minsAgo(43), readAt: minsAgo(12), acknowledgedAt: null, escalated: false },
        { staffId: 'stf_appiah', name: 'Grace Appiah', role: 'Circulating Nurse', status: 'escalated', sentAt: minsAgo(44), deliveredAt: minsAgo(44), readAt: null, acknowledgedAt: null, escalated: true, escalatedAt: minsAgo(13) },
        { staffId: 'stf_deller', name: 'Mark Deller', role: 'ODP', status: 'delivered', sentAt: minsAgo(44), deliveredAt: minsAgo(43), readAt: null, acknowledgedAt: null, escalated: false },
      ],
    },
  ],
  case_0900: [
    {
      pageId: 'page_0900_flag',
      createdAt: atToday('11:22'),
      urgent: true,
      body: 'Instrument second-count flag, Theatre 5 knee replacement: one artery forceps present before, not seen after. This is a second check — please repeat the manual WHO count now.',
      recipients: [
        { staffId: 'stf_okafor', name: 'Ms Chioma Okafor', role: 'Consultant Surgeon', status: 'acknowledged', sentAt: atToday('11:22'), deliveredAt: atToday('11:22'), readAt: atToday('11:23'), acknowledgedAt: atToday('11:24'), escalated: false },
        { staffId: 'stf_balogun', name: 'Tunde Balogun', role: 'Scrub Nurse', status: 'acknowledged', sentAt: atToday('11:22'), deliveredAt: atToday('11:22'), readAt: atToday('11:23'), acknowledgedAt: atToday('11:26'), escalated: false },
      ],
    },
    {
      pageId: 'page_0900_brief',
      createdAt: atToday('07:40'),
      urgent: false,
      body: 'Theatre 5, 09:00 — Total knee replacement, Ms Okafor. You are on this list. Reply to acknowledge.',
      recipients: [
        { staffId: 'stf_okafor', name: 'Ms Chioma Okafor', role: 'Consultant Surgeon', status: 'acknowledged', sentAt: atToday('07:40'), deliveredAt: atToday('07:40'), readAt: atToday('07:41'), acknowledgedAt: atToday('07:42'), escalated: false },
        { staffId: 'stf_rahimi', name: 'Dr Omar Rahimi', role: 'Anaesthetist', status: 'acknowledged', sentAt: atToday('07:40'), deliveredAt: atToday('07:40'), readAt: atToday('07:44'), acknowledgedAt: atToday('07:46'), escalated: false },
        { staffId: 'stf_balogun', name: 'Tunde Balogun', role: 'Scrub Nurse', status: 'acknowledged', sentAt: atToday('07:40'), deliveredAt: atToday('07:41'), readAt: atToday('07:48'), acknowledgedAt: atToday('07:50'), escalated: false },
        { staffId: 'stf_deller', name: 'Mark Deller', role: 'ODP', status: 'acknowledged', sentAt: atToday('07:40'), deliveredAt: atToday('07:40'), readAt: atToday('07:52'), acknowledgedAt: atToday('07:55'), escalated: false },
      ],
    },
  ],
};

/* ----------------------------------------------------------- conversations */

const convByCase: Record<string, Message[]> = {
  case_1400: [
    { number: '+44 7700 900312', name: 'Idris Mahama', role: 'Patient', direction: 'out', kind: 'text', body: 'Hello Mr Mahama. This is St Aldate’s theatre coordination for your gallbladder operation today at 14:00 in Theatre 2. A few things to confirm.', createdAt: hrsAgo(20), readAt: hrsAgo(19) },
    { number: '+44 7700 900312', name: 'Idris Mahama', role: 'Patient', direction: 'out', kind: 'text', body: 'Please do not eat from 02:00 and stop clear fluids by 11:00. Reply FASTING when you have done this.', createdAt: hrsAgo(20), readAt: hrsAgo(19) },
    { number: '+44 7700 900312', name: 'Idris Mahama', role: 'Patient', direction: 'in', kind: 'text', body: 'Understood, thank you. I will arrive by 12:30.', createdAt: hrsAgo(18), readAt: null },
    { number: '+44 7700 900312', name: 'Idris Mahama', role: 'Patient', direction: 'out', kind: 'text', body: 'There is an outstanding self-funded balance of £240.00. You can settle it at the admissions desk on arrival. Reply if you have any questions.', createdAt: hrsAgo(5), readAt: hrsAgo(5) },
    { number: '+44 7700 900111', name: 'Mr David Adeyemi', role: 'Consultant Surgeon', direction: 'out', kind: 'interactive', body: 'Page: Theatre 2, 14:00 case at risk — consent and balance outstanding. Acknowledge?', createdAt: minsAgo(44), readAt: minsAgo(42) },
    { number: '+44 7700 900111', name: 'Mr David Adeyemi', role: 'Consultant Surgeon', direction: 'in', kind: 'interactive', body: 'Acknowledged. I will take consent on the ward at 12:45.', createdAt: minsAgo(40), readAt: null },
  ],
  case_0900: [
    { number: '+44 7700 900142', name: 'Tunde Balogun', role: 'Scrub Nurse', direction: 'in', kind: 'image', body: 'Tray laid out, before the case.', createdAt: atToday('08:45'), readAt: atToday('08:45') },
    { number: '+44 7700 900142', name: 'Tunde Balogun', role: 'Scrub Nurse', direction: 'out', kind: 'text', body: 'Catalogue received: 6 artery forceps, 2 scalpel handles, 1 mayo scissors, 2 retractors, 1 needle holder, 10 swabs. Send the after photo when you close.', createdAt: atToday('08:46'), readAt: atToday('08:47') },
    { number: '+44 7700 900142', name: 'Tunde Balogun', role: 'Scrub Nurse', direction: 'in', kind: 'image', body: 'Tray after closing.', createdAt: atToday('11:20'), readAt: atToday('11:20') },
    { number: '+44 7700 900142', name: 'Tunde Balogun', role: 'Scrub Nurse', direction: 'out', kind: 'text', body: 'Second-count flag: 1 artery forceps present before, not seen after. This is a second check, not the count. Please repeat the manual WHO count now.', createdAt: atToday('11:22'), readAt: atToday('11:23') },
    { number: '+44 7700 900142', name: 'Tunde Balogun', role: 'Scrub Nurse', direction: 'in', kind: 'text', body: 'Found it — fell behind the drape, recovered and accounted for. Manual count now correct.', createdAt: atToday('11:26'), readAt: null },
  ],
};

/* ------------------------------------------------------------------- forms */

const formsByCase: Record<string, FormRecord[]> = {
  case_1400: [
    { formId: 'form_1400_appiah', staffName: 'Grace Appiah', role: 'Circulating Nurse', kind: 'Role handover', status: 'overdue', url: null, requestedAt: minsAgo(13) },
    { formId: 'form_1400_consent', staffName: 'Mr David Adeyemi', role: 'Consultant Surgeon', kind: 'Consent confirmation', status: 'requested', url: null, requestedAt: minsAgo(30) },
  ],
  case_0900: [
    { formId: 'form_0900_count', staffName: 'Tunde Balogun', role: 'Scrub Nurse', kind: 'Instrument count discrepancy', status: 'completed', url: '/tray-after.svg', requestedAt: atToday('11:22'), uploadedAt: atToday('11:31') },
    { formId: 'form_0900_swab', staffName: 'Grace Appiah', role: 'Circulating Nurse', kind: 'Swab count sign-off', status: 'completed', url: '/tray-before.svg', requestedAt: atToday('11:05'), uploadedAt: atToday('11:12') },
  ],
};

/* --------------------------------------------------------------- follow-ups */

const followups: Followup[] = [
  { caseId: 'case_fu_wiley', patientName: 'Margaret Wiley', procedure: 'Total knee replacement', surgeonName: 'Ms Chioma Okafor', dueAt: daysFromNow(0.1), status: 'due', lastReply: null },
  { caseId: 'case_fu_bennett', patientName: 'Grace Bennett', procedure: 'Laparoscopic cholecystectomy', surgeonName: 'Mr David Adeyemi', dueAt: minsAgo(90), status: 'overdue', lastReply: null },
  { caseId: 'case_fu_doyle', patientName: 'Fiona Doyle', procedure: 'Varicose vein surgery', surgeonName: 'Mr David Adeyemi', dueAt: hrsAgo(26), status: 'escalated', lastReply: 'My calf is hot, swollen and painful since this morning.' },
  { caseId: 'case_fu_osborne', patientName: 'Raymond Osborne', procedure: 'Inguinal hernia repair', surgeonName: 'Mr David Adeyemi', dueAt: hrsAgo(6), status: 'replied', lastReply: 'Wound looks clean, mild soreness, no fever. Walking fine.' },
  { caseId: 'case_fu_kaur', patientName: 'Simran Kaur', procedure: 'Knee arthroscopy', surgeonName: 'Ms Chioma Okafor', dueAt: daysFromNow(1), status: 'scheduled', lastReply: null },
  { caseId: 'case_fu_pratt', patientName: 'George Pratt', procedure: 'Total hip replacement', surgeonName: 'Ms Chioma Okafor', dueAt: daysFromNow(2), status: 'scheduled', lastReply: null },
];

/* ------------------------------------------------------------- mutable set */

/** Hold mutations in memory for the session so create/patch/page feel live. */
const order = ['case_0801', 'case_0900', 'case_1100', 'case_1330', 'case_1400'];

function sortByTime(ids: string[]): CaseSummary[] {
  return ids
    .map((id) => seeds[id]?.summary)
    .filter((s): s is CaseSummary => !!s)
    .sort((a, b) => a.scheduledAt.localeCompare(b.scheduledAt));
}

/* --------------------------------------------------------------------- api */

export const demoApi = {
  async me(): Promise<Me> {
    return latency(me);
  },

  async listCases(day: string): Promise<CaseSummary[]> {
    // every seeded case is scheduled for today; other days come back empty, honestly.
    if (day !== today) return latency([], 220);
    return latency(sortByTime(order));
  },

  async getCase(id: string): Promise<CaseDetail> {
    const s = seeds[id];
    if (!s) throw new Error('That case could not be found.');
    return latency({
      case: { ...s.summary, stage: s.stage, anaesthetic: s.anaesthetic, notes: s.notes },
      team: s.team,
      patient: s.patient,
      readiness: s.summary.readiness,
      checklist: s.checklist,
      tray: s.tray,
    });
  },

  async createCase(input: NewCaseInput): Promise<CaseSummary> {
    const id = `case_new_${Math.random().toString(36).slice(2, 7)}`;
    const summary: CaseSummary = {
      caseId: id,
      procedure: input.procedure,
      procedureCode: input.procedureCode,
      theatre: input.theatre,
      scheduledAt: input.scheduledAt,
      surgeonName: input.surgeonName,
      patientName: input.patientName,
      readiness: readiness(70, 'medium', [
        { key: 'rd_consent', label: 'Consent not yet signed', state: 'pending' },
        { key: 'rd_instructions', label: 'Pre-op instructions not sent', state: 'pending' },
        { key: 'rd_bloods', label: 'Pre-op bloods and group & save', state: 'done' },
      ]),
    };
    seeds[id] = {
      summary,
      stage: 'scheduled',
      team: theatre2Team,
      patient: { name: input.patientName, balancePence: 0 },
      checklist: checklist([]),
      tray: null,
    };
    if (!order.includes(id)) order.push(id);
    return latency(summary);
  },

  async patchCase(id: string, patch: CasePatch): Promise<CaseSummary> {
    const s = seeds[id];
    if (!s) throw new Error('That case could not be found.');
    s.summary = { ...s.summary, ...patch };
    if (patch.stage) s.stage = patch.stage;
    if (patch.notes !== undefined) s.notes = patch.notes;
    return latency(s.summary);
  },

  async pages(id: string): Promise<PageRecord[]> {
    return latency(pagesByCase[id] ?? []);
  },

  async sendPage(id: string, input: PageInput): Promise<PageRecord> {
    const s = seeds[id];
    const team = s?.team ?? theatre2Team;
    const rec: PageRecord = {
      pageId: `page_${Math.random().toString(36).slice(2, 7)}`,
      createdAt: new Date().toISOString(),
      urgent: input.urgent,
      body: input.body,
      recipients: team.map((m) => ({
        staffId: m.staffId,
        name: m.name,
        role: m.role,
        status: 'sent',
        sentAt: new Date().toISOString(),
        deliveredAt: null,
        readAt: null,
        acknowledgedAt: null,
        escalated: false,
      })),
    };
    pagesByCase[id] = [rec, ...(pagesByCase[id] ?? [])];
    return latency(rec);
  },

  async conversations(id: string): Promise<Message[]> {
    const m = (convByCase[id] ?? []).slice().sort((a, b) => a.createdAt.localeCompare(b.createdAt));
    return latency(m);
  },

  async forms(id: string): Promise<FormRecord[]> {
    return latency(formsByCase[id] ?? []);
  },

  async followups(): Promise<Followup[]> {
    return latency(followups);
  },

  async listStaff(): Promise<Staff[]> {
    return latency(staff);
  },

  async addStaff(input: NewStaffInput): Promise<Staff> {
    const s: Staff = {
      staffId: `stf_${Math.random().toString(36).slice(2, 7)}`,
      name: input.name,
      role: input.role,
      email: input.email,
      whatsappNumber: input.whatsappNumber,
      linked: false,
    };
    staff.push(s);
    return latency(s);
  },
};
