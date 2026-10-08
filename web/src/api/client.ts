import { API_URL, DEMO } from '../config';
import { demoApi } from './demo';
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

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/* The auth layer registers how to get a bearer token and what to do on 401. */
let tokenProvider: () => Promise<string | null> = async () => null;
let unauthorizedHandler: () => void = () => {};
export function configureAuth(p: () => Promise<string | null>, onUnauthorized: () => void) {
  tokenProvider = p;
  unauthorizedHandler = onUnauthorized;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!API_URL) throw new ApiError(0, 'VITE_API_URL is not set. Build with the deployed API URL, or use VITE_DEMO=1.');
  const token = await tokenProvider();
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new ApiError(0, "Can't reach Scrubbed. Check your connection and try again.");
  }
  if (res.status === 401) {
    unauthorizedHandler();
    throw new ApiError(401, 'Your session has expired. Please sign in again.');
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const j = await res.json();
      message = j.message ?? j.error ?? message;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/* ------------------------------------------------------------ normalisation */

type Raw = Record<string, unknown>;

function list<T>(data: unknown, keys: string[]): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === 'object') {
    for (const k of keys) {
      const v = (data as Raw)[k];
      if (Array.isArray(v)) return v as T[];
    }
  }
  return [];
}

function normaliseMe(data: unknown): Me {
  const d = data as Raw;
  const staff = (d.staff ?? d) as unknown as Me;
  return {
    name: String(staff.name ?? ''),
    role: String(staff.role ?? ''),
    hospitalId: String(staff.hospitalId ?? ''),
    email: staff.email,
  };
}

/* --------------------------------------------------------------- live API */

export interface ScrubbedApi {
  me(): Promise<Me>;
  listCases(day: string): Promise<CaseSummary[]>;
  getCase(id: string): Promise<CaseDetail>;
  createCase(input: NewCaseInput): Promise<CaseSummary>;
  patchCase(id: string, patch: CasePatch): Promise<CaseSummary>;
  pages(id: string): Promise<PageRecord[]>;
  sendPage(id: string, input: PageInput): Promise<PageRecord>;
  conversations(id: string): Promise<Message[]>;
  forms(id: string): Promise<FormRecord[]>;
  followups(): Promise<Followup[]>;
  listStaff(): Promise<Staff[]>;
  addStaff(input: NewStaffInput): Promise<Staff>;
}

const enc = encodeURIComponent;

const liveApi: ScrubbedApi = {
  async me() {
    return normaliseMe(await request<unknown>('/me'));
  },
  async listCases(day) {
    return list<CaseSummary>(await request<unknown>(`/cases?day=${enc(day)}`), ['cases', 'items', 'Items']);
  },
  async getCase(id) {
    const d = await request<Raw>(`/cases/${enc(id)}`);
    return d as unknown as CaseDetail;
  },
  async createCase(input) {
    const d = await request<Raw>('/cases', { method: 'POST', body: JSON.stringify(input) });
    return ((d.case as CaseSummary) ?? (d as unknown as CaseSummary));
  },
  async patchCase(id, patch) {
    const d = await request<Raw>(`/cases/${enc(id)}`, { method: 'PATCH', body: JSON.stringify(patch) });
    return ((d.case as CaseSummary) ?? (d as unknown as CaseSummary));
  },
  async pages(id) {
    return list<PageRecord>(await request<unknown>(`/cases/${enc(id)}/pages`), ['pages', 'items', 'Items']);
  },
  async sendPage(id, input) {
    const d = await request<Raw>(`/cases/${enc(id)}/page`, { method: 'POST', body: JSON.stringify(input) });
    return ((d.page as PageRecord) ?? (d as unknown as PageRecord));
  },
  async conversations(id) {
    const m = list<Message>(await request<unknown>(`/cases/${enc(id)}/conversations`), ['messages', 'items', 'Items']);
    return m.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  },
  async forms(id) {
    return list<FormRecord>(await request<unknown>(`/cases/${enc(id)}/forms`), ['forms', 'items', 'Items']);
  },
  async followups() {
    return list<Followup>(await request<unknown>('/followups'), ['cases', 'items', 'Items']);
  },
  async listStaff() {
    return list<Staff>(await request<unknown>('/staff'), ['staff', 'items', 'Items']);
  },
  async addStaff(input) {
    const d = await request<Raw>('/staff', { method: 'POST', body: JSON.stringify(input) });
    return ((d.staff as Staff) ?? (d as unknown as Staff));
  },
};

export const api: ScrubbedApi = DEMO ? (demoApi as ScrubbedApi) : liveApi;
