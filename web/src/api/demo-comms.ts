import { atToday, daysFromNow, hrsAgo, minsAgo } from './demo-data';
import type { Followup, FormRecord, Message, PageRecord } from './types';

/* ------------------------------------------------------------------ paging */

export const pagesByCase: Record<string, PageRecord[]> = {
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

export const convByCase: Record<string, Message[]> = {
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

export const formsByCase: Record<string, FormRecord[]> = {
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

export const followups: Followup[] = [
  { caseId: 'case_fu_wiley', patientName: 'Margaret Wiley', procedure: 'Total knee replacement', surgeonName: 'Ms Chioma Okafor', dueAt: daysFromNow(0.1), status: 'due', lastReply: null },
  { caseId: 'case_fu_bennett', patientName: 'Grace Bennett', procedure: 'Laparoscopic cholecystectomy', surgeonName: 'Mr David Adeyemi', dueAt: minsAgo(90), status: 'overdue', lastReply: null },
  { caseId: 'case_fu_doyle', patientName: 'Fiona Doyle', procedure: 'Varicose vein surgery', surgeonName: 'Mr David Adeyemi', dueAt: hrsAgo(26), status: 'escalated', lastReply: 'My calf is hot, swollen and painful since this morning.' },
  { caseId: 'case_fu_osborne', patientName: 'Raymond Osborne', procedure: 'Inguinal hernia repair', surgeonName: 'Mr David Adeyemi', dueAt: hrsAgo(6), status: 'replied', lastReply: 'Wound looks clean, mild soreness, no fever. Walking fine.' },
  { caseId: 'case_fu_kaur', patientName: 'Simran Kaur', procedure: 'Knee arthroscopy', surgeonName: 'Ms Chioma Okafor', dueAt: daysFromNow(1), status: 'scheduled', lastReply: null },
  { caseId: 'case_fu_pratt', patientName: 'George Pratt', procedure: 'Total hip replacement', surgeonName: 'Ms Chioma Okafor', dueAt: daysFromNow(2), status: 'scheduled', lastReply: null },
];
