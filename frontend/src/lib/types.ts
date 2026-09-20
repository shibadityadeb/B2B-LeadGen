/** Mirrors the backend Pydantic schemas (backend/app/schemas). */

export type RunStatus = "queued" | "running" | "completed" | "failed";
export type CompanyStatus =
  | "discovered"
  | "researching"
  | "researched"
  | "research_failed";

export interface Target {
  id: number;
  name: string;
  industry: string;
  location: string | null;
  country: string | null;
  company_size: string | null;
  keywords: string[];
  search_context: string | null;
  created_at: string;
  updated_at: string;
}

export interface TargetListItem extends Target {
  companies_count: number;
  last_run_at: string | null;
  last_run_status: RunStatus | null;
  last_run_id: number | null;
}

export interface TargetInput {
  name: string;
  industry: string;
  location?: string | null;
  country?: string | null;
  company_size?: string | null;
  keywords: string[];
  search_context?: string | null;
}

export interface SearchQuery {
  id: number;
  query: string;
  template: string | null;
  provider: string | null;
  status: string;
  results_count: number;
  error_message: string | null;
  executed_at: string | null;
}

export interface SearchResult {
  id: number;
  title: string | null;
  url: string;
  snippet: string | null;
  source_engine: string | null;
  position: number | null;
  extracted_domain: string | null;
  accepted: boolean;
  rejection_reason: string | null;
  discovered_at: string | null;
}

export interface DiscoveryRun {
  id: number;
  target_id: number;
  status: RunStatus;
  stage: string;
  progress: number;
  search_provider: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  queries_count: number;
  results_count: number;
  unique_domains_count: number;
  new_companies_count: number;
  duplicate_companies_count: number;
  rejected_results_count: number;
  failed_queries_count: number;
  error_message: string | null;
  errors: { stage?: string; query?: string; message?: string }[];
  target_name: string | null;
  target_industry: string | null;
  target_location: string | null;
}

export interface DiscoveryRunDetail extends DiscoveryRun {
  queries: SearchQuery[];
  results: SearchResult[];
}

export interface Company {
  id: number;
  name: string;
  canonical_domain: string;
  website_url: string;
  description: string | null;
  industry: string | null;
  location: string | null;
  country: string | null;
  company_size: string | null;
  status: CompanyStatus;
  crawl_error: string | null;
  first_discovery_run_id: number | null;
  last_researched_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CompanyListItem extends Company {
  sources_count: number;
}

export interface CompanySource {
  id: number;
  url: string;
  title: string | null;
  snippet: string | null;
  source_type: string;
  source_engine: string | null;
  discovery_run_id: number | null;
  target_id: number | null;
  discovered_at: string | null;
}

export interface CompanyPage {
  id: number;
  url: string;
  page_type: string;
  title: string | null;
  content_length: number;
  status: "success" | "failed" | "skipped";
  http_status: number | null;
  error_message: string | null;
  crawled_at: string | null;
}

export interface CompanySummary {
  pages_found: string[];
  page_count: number;
  successful_pages: number;
  failed_pages: number;
  homepage_title: string | null;
  total_content_chars: number;
  emails: string[];
  phones: string[];
  facts: string[];
}

export interface CompanyDetail extends Company {
  sources: CompanySource[];
  pages: CompanyPage[];
  summary: CompanySummary;
}

export interface CompanyFilterOptions {
  industries: string[];
  locations: string[];
  statuses: string[];
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ComponentStatus {
  name: string;
  provider: string;
  connected: boolean;
  detail: string | null;
  optional: boolean;
}

export interface SystemStatus {
  healthy: boolean;
  environment: string;
  components: ComponentStatus[];
  configuration: Record<string, string | number | boolean>;
}

export interface DashboardStats {
  targets_count: number;
  companies_count: number;
  researched_count: number;
  sources_count: number;
  pages_count: number;
  runs_count: number;
  runs_by_status: Record<string, number>;
  recent_runs: {
    id: number;
    target_id: number;
    target_name: string;
    industry: string;
    location: string | null;
    status: RunStatus;
    progress: number;
    companies_found: number;
    created_at: string;
    completed_at: string | null;
  }[];
  recent_companies: {
    id: number;
    name: string;
    canonical_domain: string;
    industry: string | null;
    location: string | null;
    status: CompanyStatus;
    created_at: string;
  }[];

  // --- phase 2 ---
  research_runs_count: number;
  research_runs_by_status: Record<string, number>;
  evidence_count: number;
  fresh_evidence_count: number;
  signals_count: number;
  opportunities_count: number;
  decision_makers_count: number;
  capabilities_count: number;
}

/* -------------------------------------------------------------------------
   Phase 2: research, evidence, signals, opportunities, decision makers
   ------------------------------------------------------------------------- */

export type ResearchStatus =
  | "not_started"
  | "queued"
  | "researching"
  | "analyzing"
  | "completed"
  | "failed";

export type EpistemicStatus = "known" | "inferred" | "possible" | "unknown";
export type FreshnessLevel = "recent" | "active" | "older" | "stale" | "unknown";
export type ConfidenceLevel = "high" | "medium" | "low";
export type ObservationState = "new" | "still_present" | "updated" | "not_found";
export type OpportunityStatus = "candidate" | "supported" | "uncertain" | "dismissed";

export interface ConfidenceBreakdown {
  score?: number;
  level?: string;
  components?: Record<string, number>;
  weights?: Record<string, number>;
  notes?: string[];
  distinct_sources?: number;
}

export interface EvidenceSourceRef {
  id: number;
  url: string;
  title: string | null;
  type: string | null;
  reliability: string | null;
}

export interface Evidence {
  id: number;
  claim: string;
  excerpt: string | null;
  evidence_type: string;
  epistemic_status: EpistemicStatus;
  normalized_value: Record<string, unknown>;
  confidence: number;
  confidence_level: ConfidenceLevel;
  confidence_components: ConfidenceBreakdown;
  observation_state: ObservationState;
  times_observed: number;
  published_at: string | null;
  observed_at: string | null;
  extractor: string;
  source: EvidenceSourceRef | null;
  freshness: FreshnessLevel | null;
  age_days: number | null;
  /** "published_at" | "observed_at" | "none" — how freshness was determined. */
  freshness_basis: string | null;
}

export interface Signal {
  id: number;
  signal_type: string;
  title: string;
  description: string;
  strength: number;
  freshness: FreshnessLevel;
  confidence: number;
  confidence_level: ConfidenceLevel;
  confidence_components: ConfidenceBreakdown;
  evidence_count: number;
  observation_state: ObservationState;
  latest_evidence_at: string | null;
  evidence_ids: number[];
}

export interface Opportunity {
  id: number;
  company_id: number;
  capability_id: number;
  capability_name: string | null;
  capability_category: string | null;
  title: string;
  description: string;
  why_relevant: string;
  confidence: number;
  confidence_level: ConfidenceLevel;
  confidence_components: ConfidenceBreakdown;
  freshness: FreshnessLevel;
  status: OpportunityStatus;
  evidence_count: number;
  observation_state: ObservationState;
  evidence_ids: number[];
  signal_ids: number[];
  created_at: string;
  updated_at: string;
}

export interface DecisionMaker {
  id: number;
  name: string | null;
  role: string;
  role_category: string | null;
  email: string | null;
  phone: string | null;
  profile_url: string | null;
  verification_status: string;
  confidence: number;
  confidence_level: ConfidenceLevel;
  excerpt: string | null;
  observation_state: ObservationState;
  source_url: string | null;
  created_at: string;
}

export interface ResearchSource {
  id: number;
  url: string;
  domain: string | null;
  title: string | null;
  source_type: string;
  source_reliability: string;
  retrieval_status: string;
  published_at: string | null;
  discovered_at: string | null;
  retrieved_at: string | null;
  content_length: number;
  error_message: string | null;
}

export interface Contradiction {
  id: number;
  subject: string;
  status: string;
  explanation: string | null;
  evidence_a_id: number;
  evidence_b_id: number;
  preferred_evidence_id: number | null;
}

export interface ResearchRun {
  id: number;
  company_id: number;
  status: ResearchStatus;
  stage: string;
  progress: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  sources_discovered: number;
  sources_retrieved: number;
  sources_failed: number;
  evidence_count: number;
  new_evidence_count: number;
  signals_count: number;
  opportunities_count: number;
  decision_makers_count: number;
  contradictions_count: number;
  search_provider: string | null;
  crawler_provider: string | null;
  llm_provider: string | null;
  llm_used: boolean;
  error_message: string | null;
  errors: { stage?: string; message?: string; stats?: Record<string, number> }[];
  company_name: string | null;
  company_domain: string | null;
}

export interface ResearchRunDetail extends ResearchRun {
  sources: ResearchSource[];
  brief_markdown: string | null;
  /** The structured profile the markdown was rendered from. */
  brief_profile: Record<string, unknown> | null;
}

export interface ResearchBrief {
  research_run_id: number;
  markdown: string;
  profile: Record<string, unknown>;
  generated_by: string;
  created_at: string;
}

export interface CompanyResearchState {
  company_id: number;
  research_status: ResearchStatus;
  latest_run: ResearchRun | null;
  runs: ResearchRun[];
  counts: Record<string, number>;
  brief: ResearchBrief | null;
}

export interface UbmCapability {
  id: number;
  slug: string;
  name: string;
  description: string;
  category: string | null;
  signal_types: string[];
  keywords: string[];
  rationale_template: string | null;
  weight: number;
  active: boolean;
  is_seed: boolean;
  created_at: string;
  updated_at: string;
}

export interface SignalTypeOption {
  value: string;
  label: string;
}

export interface BulkResearchResponse {
  queued: ResearchRun[];
  skipped: { company_id: number; company_name?: string; reason: string; run_id?: number }[];
}

/* -------------------------------------------------------------------------
   Phase 3: outreach, approval, Gmail drafts, follow-ups
   ------------------------------------------------------------------------- */

export type OutreachStatus =
  | "draft"
  | "review"
  | "approved"
  | "gmail_draft_created"
  | "sent"
  | "follow_up_due"
  | "completed"
  | "cancelled"
  | "rejected";

export type OutreachTone = "professional" | "conversational" | "direct" | "warm";
export type MessageLength = "short" | "medium";
export type OutreachObjective =
  | "start_conversation"
  | "request_short_call"
  | "share_idea"
  | "explore_partnership"
  | "introduce_capability"
  | "follow_up"
  | "reconnect";

export type OutcomeStatus =
  | "no_response"
  | "replied"
  | "interested"
  | "not_interested"
  | "meeting_scheduled"
  | "opportunity_won"
  | "opportunity_lost"
  | "do_not_contact";

export type OutcomeReason =
  | "wrong_opportunity"
  | "wrong_person"
  | "wrong_company"
  | "timing"
  | "already_has_provider"
  | "no_budget"
  | "not_relevant"
  | "other";

export interface ValidationIssue {
  code: string;
  message: string;
  context: string | null;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
}

export interface PersonalizationPoint {
  observation: string;
  excerpt: string;
  evidence_ids: number[];
  evidence_type: string;
  source_url: string | null;
  published_at: string | null;
  freshness: string;
  freshness_basis: string;
  epistemic_status: string;
}

export interface OutreachStrategy {
  objective: string;
  primary_signal: string | null;
  relevant_capability: string;
  recipient_role: string | null;
  personalization_points: string[];
  call_to_action: string;
  tone: string;
  message_length: string;
  notes: string[];
}

export interface PersonalizationData {
  recipient: {
    decision_maker_id: number | null;
    name: string | null;
    role: string | null;
    role_category: string | null;
    email: string | null;
    verification_status: string | null;
    source_url: string | null;
  };
  company_reference: PersonalizationPoint | null;
  business_signal: {
    signal_id: number;
    signal_type: string;
    title: string;
    freshness: string;
    evidence_ids: number[];
  } | null;
  relevant_ubm_capability: {
    id: number;
    name: string;
    category: string | null;
    description: string;
  };
  conversation_angle: string;
  points: PersonalizationPoint[];
  uncertainties: string[];
}

export interface ClaimEvidenceRef {
  evidence_id: number;
  claim: string | null;
  excerpt: string | null;
  source_url: string | null;
  source_title: string | null;
  published_at: string | null;
  freshness: string | null;
  freshness_basis: string | null;
}

export interface OutreachClaim {
  id: number;
  text: string;
  kind: string;
  requires_evidence: boolean;
  evidence: ClaimEvidenceRef[];
}

export interface OutreachVersion {
  id: number;
  version_number: number;
  subject: string | null;
  body: string | null;
  generation_method: string;
  is_active: boolean;
  created_at: string;
  validation: ValidationResult | Record<string, never>;
  claims: OutreachClaim[];
}

export interface OutreachOutcomeEntry {
  id: number;
  status: string;
  reason: string | null;
  notes: string | null;
  recorded_by: string | null;
  created_at: string;
}

export interface Outreach {
  id: number;
  company_id: number;
  opportunity_id: number | null;
  decision_maker_id: number | null;
  campaign_id: number | null;
  parent_outreach_id: number | null;
  follow_up_number: number;

  status: OutreachStatus;
  objective: string;
  tone: OutreachTone;
  message_length: MessageLength;

  to_email: string | null;
  to_name: string | null;
  cc: string | null;
  bcc: string | null;

  subject: string | null;
  body: string | null;
  ai_generated_subject: string | null;
  ai_generated_body: string | null;
  user_edited: boolean;
  generated_by: string;

  strategy: OutreachStrategy | Record<string, never>;
  personalization: PersonalizationData | Record<string, never>;
  validation: ValidationResult | Record<string, never>;

  gmail_draft_id: string | null;
  gmail_draft_url: string | null;
  approved_at: string | null;
  gmail_draft_created_at: string | null;
  sent_at: string | null;
  next_follow_up_at: string | null;

  outcome_status: OutcomeStatus | null;
  outcome_reason: string | null;
  outcome_notes: string | null;
  outcome_updated_at: string | null;

  active_version_id: number | null;
  owner: string | null;
  created_at: string;
  updated_at: string;

  company_name: string | null;
  company_domain: string | null;
  company_industry: string | null;
  opportunity_title: string | null;
  capability_name: string | null;
  campaign_name: string | null;
  recipient_role: string | null;
  follow_up_due: boolean;
}

export interface OutreachDetail extends Outreach {
  versions: OutreachVersion[];
  outcomes: OutreachOutcomeEntry[];
  follow_ups: Outreach[];
  audit: {
    id: number;
    action: string;
    actor: string | null;
    detail: Record<string, unknown>;
    created_at: string;
  }[];
}

export interface SenderProfile {
  id: number;
  name: string;
  role: string | null;
  company: string;
  email: string | null;
  website: string | null;
  signature: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface GmailConnection {
  connected: boolean;
  configured: boolean;
  account_email: string | null;
  status: string | null;
  scopes: string[];
  connected_at: string | null;
  needs_reauth: boolean;
  detail: string | null;
}

export interface OutreachCampaign {
  id: number;
  name: string;
  description: string | null;
  target_id: number | null;
  sender_profile_id: number | null;
  tone: string;
  message_length: string;
  follow_up_intervals: number[];
  status: string;
  owner: string | null;
  created_at: string;
  updated_at: string;
  target_name: string | null;
  outreach_counts: Record<string, number>;
  outreach_total: number;
}

export interface OutreachAnalytics {
  opportunities_total: number;
  outreach_total: number;
  by_status: Record<string, number>;
  by_outcome: Record<string, number>;
  drafts: number;
  awaiting_review: number;
  approved: number;
  gmail_drafts: number;
  marked_sent: number;
  follow_ups_due: number;
  replies: number;
  meetings: number;
  won: number;
  lost: number;
  edited_before_approval: number;
  versions_total: number;
  approval_rate: number | null;
  reply_rate: number | null;
  rate_note: string | null;
  recent: Outreach[];
}
