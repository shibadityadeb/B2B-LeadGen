import type {
  BulkResearchResponse,
  Company,
  CompanyDetail,
  CompanyFilterOptions,
  CompanyListItem,
  DashboardStats,
  DiscoveryRun,
  DiscoveryRunDetail,
  CompanyResearchState,
  Contradiction,
  DecisionMaker,
  Evidence,
  Opportunity,
  OpportunityStatus,
  Paginated,
  ResearchBrief,
  ResearchRun,
  ResearchRunDetail,
  ResearchSource,
  Signal,
  GmailConnection,
  MessageLength,
  OutcomeReason,
  OutcomeStatus,
  Outreach,
  OutreachAnalytics,
  OutreachCampaign,
  OutreachDetail,
  OutreachTone,
  SenderProfile,
  SignalTypeOption,
  SystemStatus,
  UbmCapability,
  Target,
  TargetInput,
  TargetListItem,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** An error carrying the backend's structured error body. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string = "error",
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      `Cannot reach the API at ${BASE_URL}. Is the backend running?`,
      0,
      "network_error",
    );
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  const body = text ? safeJson(text) : null;

  if (!response.ok) {
    const message =
      (body as { message?: string })?.message ??
      `Request failed with status ${response.status}.`;
    throw new ApiError(
      message,
      response.status,
      (body as { code?: string })?.code ?? "error",
      (body as { details?: Record<string, unknown> })?.details ?? {},
    );
  }

  return body as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function query(params: Record<string, string | number | undefined | null>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export const api = {
  baseUrl: BASE_URL,

  // --- system ---
  dashboard: () => request<DashboardStats>("/api/dashboard"),
  status: () => request<SystemStatus>("/api/status"),

  // --- targets ---
  listTargets: () => request<TargetListItem[]>("/api/targets"),
  getTarget: (id: number) => request<Target>(`/api/targets/${id}`),
  createTarget: (payload: TargetInput) =>
    request<Target>("/api/targets", { method: "POST", body: JSON.stringify(payload) }),
  previewQueries: (payload: TargetInput) =>
    request<{ queries: string[] }>("/api/targets/preview", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteTarget: (id: number) =>
    request<void>(`/api/targets/${id}`, { method: "DELETE" }),
  startDiscovery: (id: number) =>
    request<DiscoveryRun>(`/api/targets/${id}/discover`, { method: "POST" }),

  // --- runs ---
  listRuns: (params: { page?: number; page_size?: number; target_id?: number } = {}) =>
    request<Paginated<DiscoveryRun>>(`/api/runs${query(params)}`),
  getRun: (id: number) => request<DiscoveryRunDetail>(`/api/runs/${id}`),

  // --- companies ---
  listCompanies: (
    params: {
      page?: number;
      page_size?: number;
      search?: string;
      industry?: string;
      location?: string;
      status?: string;
      target_id?: number;
      discovered_after?: string;
      discovered_before?: string;
    } = {},
  ) => request<Paginated<CompanyListItem>>(`/api/companies${query(params)}`),
  companyFilters: () => request<CompanyFilterOptions>("/api/companies/filters"),
  getCompany: (id: number) => request<CompanyDetail>(`/api/companies/${id}`),
  crawlCompany: (id: number) =>
    request<Company>(`/api/companies/${id}/crawl`, { method: "POST" }),

  // --- phase 2: research ---
  startResearch: (id: number) =>
    request<ResearchRun>(`/api/companies/${id}/research`, { method: "POST" }),
  bulkResearch: (companyIds: number[]) =>
    request<BulkResearchResponse>("/api/companies/research/bulk", {
      method: "POST",
      body: JSON.stringify({ company_ids: companyIds }),
    }),
  companyResearch: (id: number) =>
    request<CompanyResearchState>(`/api/companies/${id}/research`),
  companyEvidence: (id: number, params: { ids?: number[]; evidence_type?: string } = {}) =>
    request<Evidence[]>(
      `/api/companies/${id}/evidence${query({
        ids: params.ids?.length ? params.ids.join(",") : undefined,
        evidence_type: params.evidence_type,
      })}`,
    ),
  companySignals: (id: number) => request<Signal[]>(`/api/companies/${id}/signals`),
  companyOpportunities: (id: number) =>
    request<Opportunity[]>(`/api/companies/${id}/opportunities`),
  companyDecisionMakers: (id: number) =>
    request<DecisionMaker[]>(`/api/companies/${id}/decision-makers`),
  companyResearchSources: (id: number) =>
    request<ResearchSource[]>(`/api/companies/${id}/research-sources`),
  companyContradictions: (id: number) =>
    request<Contradiction[]>(`/api/companies/${id}/contradictions`),
  companyBrief: (id: number) => request<ResearchBrief>(`/api/companies/${id}/brief`),

  listResearchRuns: (params: { page?: number; page_size?: number } = {}) =>
    request<Paginated<ResearchRun>>(`/api/research-runs${query(params)}`),
  getResearchRun: (id: number) => request<ResearchRunDetail>(`/api/research-runs/${id}`),

  updateOpportunityStatus: (id: number, status: OpportunityStatus) =>
    request<Opportunity>(`/api/opportunities/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  // --- phase 2: UBM capabilities ---
  listCapabilities: () => request<UbmCapability[]>("/api/ubm/capabilities"),
  listSignalTypes: () => request<SignalTypeOption[]>("/api/ubm/signal-types"),
  createCapability: (payload: {
    name: string;
    description: string;
    category?: string | null;
    signal_types: string[];
    rationale_template?: string | null;
  }) =>
    request<UbmCapability>("/api/ubm/capabilities", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateCapability: (id: number, payload: Partial<UbmCapability>) =>
    request<UbmCapability>(`/api/ubm/capabilities/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  // --- phase 3: outreach ---
  createOutreach: (
    opportunityId: number,
    payload: {
      decision_maker_id?: number | null;
      campaign_id?: number | null;
      tone?: OutreachTone;
      message_length?: MessageLength;
      objective?: string | null;
    } = {},
  ) =>
    request<Outreach>(`/api/opportunities/${opportunityId}/outreach`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listOutreach: (
    params: {
      page?: number;
      page_size?: number;
      status?: string;
      company_id?: number;
      campaign_id?: number;
      opportunity_id?: number;
      owner?: string;
      search?: string;
      follow_up_due?: boolean;
      created_after?: string;
    } = {},
  ) =>
    request<Paginated<Outreach>>(
      `/api/outreach${query({ ...params, follow_up_due: params.follow_up_due ? "true" : undefined })}`,
    ),
  getOutreach: (id: number) => request<OutreachDetail>(`/api/outreach/${id}`),
  updateOutreach: (
    id: number,
    payload: {
      subject?: string;
      body?: string;
      to_email?: string;
      to_name?: string;
      cc?: string;
      bcc?: string;
    },
  ) =>
    request<Outreach>(`/api/outreach/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  regenerateOutreach: (
    id: number,
    payload: { tone?: OutreachTone; message_length?: MessageLength; objective?: string } = {},
  ) =>
    request<Outreach>(`/api/outreach/${id}/regenerate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  resetOutreach: (id: number) =>
    request<Outreach>(`/api/outreach/${id}/reset`, { method: "POST" }),
  activateVersion: (id: number, versionId: number) =>
    request<Outreach>(`/api/outreach/${id}/versions/activate`, {
      method: "POST",
      body: JSON.stringify({ version_id: versionId }),
    }),
  approveOutreach: (id: number) =>
    request<Outreach>(`/api/outreach/${id}/approve`, { method: "POST" }),
  rejectOutreach: (id: number, reason?: string) =>
    request<Outreach>(`/api/outreach/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? null }),
    }),
  cancelOutreach: (id: number) =>
    request<Outreach>(`/api/outreach/${id}/cancel`, { method: "POST" }),
  createGmailDraft: (id: number, forceNew = false) =>
    request<Outreach>(`/api/outreach/${id}/gmail-draft`, {
      method: "POST",
      body: JSON.stringify({ force_new: forceNew }),
    }),
  markSent: (id: number) =>
    request<Outreach>(`/api/outreach/${id}/mark-sent`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  createFollowUpDraft: (id: number) =>
    request<Outreach>(`/api/outreach/${id}/follow-up-draft`, { method: "POST" }),
  updateOutcome: (
    id: number,
    payload: { status: OutcomeStatus; reason?: OutcomeReason | null; notes?: string | null },
  ) =>
    request<Outreach>(`/api/outreach/${id}/outcome`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  // --- phase 3: sender, gmail, campaigns, analytics ---
  getSenderProfile: () => request<SenderProfile>("/api/sender-profile"),
  updateSenderProfile: (payload: Partial<SenderProfile>) =>
    request<SenderProfile>("/api/sender-profile", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  gmailStatus: () => request<GmailConnection>("/api/gmail/status"),
  gmailAuthorizeUrl: () =>
    request<{ authorization_url: string }>("/api/gmail/authorize"),
  gmailDisconnect: () =>
    request<GmailConnection>("/api/gmail/disconnect", { method: "POST" }),

  listCampaigns: () => request<OutreachCampaign[]>("/api/campaigns"),
  createCampaign: (payload: {
    name: string;
    description?: string | null;
    target_id?: number | null;
    tone?: OutreachTone;
    message_length?: MessageLength;
    follow_up_intervals?: number[];
  }) =>
    request<OutreachCampaign>("/api/campaigns", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getCampaign: (id: number) => request<OutreachCampaign>(`/api/campaigns/${id}`),
  prepareCampaignOutreach: (id: number, opportunityIds: number[]) =>
    request<{ created: Outreach[]; skipped: { opportunity_id: number; reason: string }[] }>(
      `/api/campaigns/${id}/prepare`,
      { method: "POST", body: JSON.stringify({ opportunity_ids: opportunityIds }) },
    ),

  outreachAnalytics: () => request<OutreachAnalytics>("/api/outreach-analytics"),
};

/** SWR fetcher keyed by a tuple of [name, ...args]. */
export const fetcher = <T>(fn: () => Promise<T>) => fn;
