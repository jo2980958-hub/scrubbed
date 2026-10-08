/* ------------------------------------------------------------------ staff */

export type Role =
  | 'Coordinator'
  | 'Consultant Surgeon'
  | 'Registrar'
  | 'Anaesthetist'
  | 'Scrub Nurse'
  | 'Circulating Nurse'
  | 'ODP'
  | 'Charge Nurse';

export interface Me {
  name: string;
  role: Role | string;
  hospitalId: string;
  email?: string;
}

export interface Staff {
  staffId: string;
  name: string;
  role: Role | string;
  email: string;
  whatsappNumber: string;
  linked?: boolean;
}

export interface NewStaffInput {
  name: string;
  role: string;
  email: string;
  whatsappNumber: string;
}

/* --------------------------------------------------------------- readiness */

/** How exposed to a day-of cancellation a case is. 'none' means ready. */
export type Risk = 'none' | 'low' | 'medium' | 'high';

export interface ReadinessItem {
  key: string;
  label: string;
  /** done = satisfied, pending = outstanding, blocked = actively holding the case. */
  state: 'done' | 'pending' | 'blocked';
  detail?: string;
}

export interface Readiness {
  /** 0-100, deterministic score from the spine. */
  score: number;
  isReady: boolean;
  risk: Risk;
  /** Short labels of what is still outstanding. */
  outstanding: string[];
  items?: ReadinessItem[];
}

/* ------------------------------------------------------------------- cases */

export interface CaseSummary {
  caseId: string;
  procedure: string;
  procedureCode?: string;
  theatre: string;
  scheduledAt: string;
  durationMins?: number;
  surgeonName: string;
  patientName?: string;
  readiness: Readiness;
}

export type CaseStage = 'scheduled' | 'in-theatre' | 'recovery' | 'complete';

export interface CaseFull extends CaseSummary {
  stage?: CaseStage;
  anaesthetic?: string;
  notes?: string;
}

/* --------------------------------------------------------------- checklist */

export type ChecklistPhase = 'sign-in' | 'time-out' | 'sign-out';

export interface ChecklistItem {
  key: string;
  label: string;
  phase: ChecklistPhase;
  done: boolean;
  confirmedBy?: string;
  confirmedAt?: string;
}

export interface Checklist {
  items: ChecklistItem[];
}

/* ------------------------------------------------------ instrument tray */

export interface TrayLine {
  item: string;
  count: number;
  /** 0-1 model confidence on this line. */
  confidence: number;
}

export interface TrayDiff {
  item: string;
  before: number;
  after: number;
  /** after - before; negative means possibly unaccounted for. */
  delta: number;
  flagged: boolean;
}

export interface Tray {
  before: TrayLine[];
  after: TrayLine[];
  diff: TrayDiff[];
  beforePhotoUrl?: string | null;
  afterPhotoUrl?: string | null;
  beforeAt?: string | null;
  afterAt?: string | null;
  /** Human acknowledgement of the second-count result. */
  acknowledgedBy?: string | null;
  acknowledgedAt?: string | null;
}

/* ------------------------------------------------------------------ patient */

export interface Patient {
  name: string;
  balancePence: number;
  dateOfBirth?: string;
  mrn?: string;
  phone?: string;
}

/* -------------------------------------------------------------- case detail */

export interface TeamMember {
  staffId: string;
  name: string;
  role: Role | string;
}

export interface CaseDetail {
  case: CaseFull;
  team: TeamMember[];
  patient: Patient;
  readiness: Readiness;
  checklist: Checklist;
  tray: Tray | null;
}

/* ------------------------------------------------------------------ paging */

export type DeliveryStatus = 'queued' | 'sent' | 'delivered' | 'read' | 'acknowledged' | 'failed';

export interface PageRecipient {
  staffId?: string;
  name: string;
  role: Role | string;
  status: DeliveryStatus;
  sentAt?: string | null;
  deliveredAt?: string | null;
  readAt?: string | null;
  acknowledgedAt?: string | null;
  /** Escalated to a voice call after the acknowledgement window. */
  escalated: boolean;
  escalatedAt?: string | null;
}

export interface PageRecord {
  pageId: string;
  body: string;
  createdAt: string;
  urgent: boolean;
  recipients: PageRecipient[];
}

/* ----------------------------------------------------------- conversations */

export type Direction = 'in' | 'out';

export interface Message {
  number: string;
  name: string;
  role?: string;
  direction: Direction;
  body: string;
  createdAt: string;
  readAt?: string | null;
  kind?: 'text' | 'interactive' | 'audio' | 'document' | 'image';
}

/* ------------------------------------------------------------------- forms */

export type FormStatus = 'requested' | 'sent' | 'completed' | 'overdue';

export interface FormRecord {
  formId: string;
  staffName: string;
  role?: string;
  kind: string;
  status: FormStatus;
  url?: string | null;
  requestedAt?: string | null;
  uploadedAt?: string | null;
}

/* --------------------------------------------------------------- follow-ups */

export type FollowupStatus = 'scheduled' | 'due' | 'overdue' | 'replied' | 'escalated' | 'closed';

export interface Followup {
  caseId: string;
  patientName: string;
  procedure: string;
  dueAt: string;
  status: FollowupStatus;
  surgeonName?: string;
  lastReply?: string | null;
}

/* ------------------------------------------------------------------ inputs */

export interface NewCaseInput {
  procedure: string;
  procedureCode?: string;
  theatre: string;
  scheduledAt: string;
  surgeonName: string;
  patientName: string;
}

export interface CasePatch {
  procedure?: string;
  theatre?: string;
  scheduledAt?: string;
  surgeonName?: string;
  stage?: CaseStage;
  notes?: string;
}

export interface PageInput {
  body: string;
  urgent: boolean;
}
