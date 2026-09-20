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
