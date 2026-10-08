import {
  checklist,
  latency,
  me,
  order,
  readiness,
  seeds,
  sortByTime,
  staff,
  theatre2Team,
  today,
} from './demo-data';
import { convByCase, followups, formsByCase, pagesByCase } from './demo-comms';
import type {
  CaseDetail,
  CasePatch,
  CaseSummary,
  Followup,
  FormRecord,
  Me,
  Message,
  NewCaseInput,
  NewStaffInput,
  PageInput,
  PageRecord,
  Staff,
} from './types';

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
        status: 'sent' as const,
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
