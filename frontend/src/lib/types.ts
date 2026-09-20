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
}
