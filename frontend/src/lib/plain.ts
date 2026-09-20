/**
 * Plain-English labels for the internal vocabulary.
 *
 * The person operating this is a marketer, not an engineer. They should never
 * have to learn what "epistemic status", "freshness basis" or "deterministic
 * extraction" mean. The underlying model keeps its precise names; this module
 * is the only place that decides how those appear on screen.
 */

/** How firmly something is established. */
export const CERTAINTY: Record<string, { label: string; help: string }> = {
  known: {
    label: "Confirmed",
    help: "Stated directly on the page we read.",
  },
  inferred: {
    label: "Suggested",
    help: "Not stated outright — we worked it out from the page.",
  },
  possible: {
    label: "Planned",
    help: "Described as something they intend to do, not something already done.",
  },
  unknown: {
    label: "Unclear",
    help: "The pages we read do not settle this.",
  },
};

/** How recent something is. */
export const RECENCY: Record<string, { label: string; help: string }> = {
  recent: { label: "Recent", help: "Within the last month." },
  active: { label: "Fairly recent", help: "Within the last three months." },
  older: { label: "Older", help: "Within the last year." },
  stale: { label: "Old", help: "More than a year ago." },
  unknown: { label: "Date unknown", help: "The page does not say when this happened." },
};

/** Shown when a date came from when we fetched the page, not from the page. */
export const ESTIMATED_DATE_HELP =
  "The page does not show a date, so this is when we found it — not necessarily when it happened.";

/** How well supported a conclusion is. */
export const STRENGTH: Record<string, { label: string; help: string }> = {
  high: { label: "Well supported", help: "Backed by strong, recent, direct sources." },
  medium: { label: "Moderately supported", help: "Reasonable support, with some gaps." },
  low: { label: "Lightly supported", help: "Thin evidence — treat with care." },
};

/** Whether we still see something on the web. */
export const VISIBILITY: Record<string, { label: string; help: string }> = {
  new: { label: "New", help: "Found for the first time in the latest check." },
  updated: { label: "Updated", help: "Found again, with different wording." },
  still_present: { label: "Still there", help: "Found again in the latest check." },
  not_found: {
    label: "No longer visible",
    help: "We could not find this in the latest check. Kept on record, but do not rely on it.",
  },
};

/** Where a piece of information came from. */
export const SOURCE_TRUST: Record<string, { label: string; help: string }> = {
  first_party: { label: "The company's own site", help: "Published by the company itself." },
  press: { label: "News or press", help: "Reported by a news outlet or press release." },
  third_party: { label: "Another website", help: "Published by someone else." },
  aggregated: { label: "Listing site", help: "A site that republishes other people's information." },
  unknown: { label: "Unclear source", help: "We could not tell who published this." },
};

/** How confident we are that a named person really holds that role. */
export const PERSON_TRUST: Record<string, { label: string; help: string }> = {
  public_company_source: {
    label: "From the company's site",
    help: "This name and role were published by the company.",
  },
  public_third_party: {
    label: "From another site",
    help: "Published somewhere other than the company's own site.",
  },
  role_only: {
    label: "Role only — no name published",
    help: "We found the role but no name. We do not guess names.",
  },
  unverified: { label: "Unverified", help: "We could not confirm this." },
};

/** What an opportunity's status means. */
export const OPPORTUNITY_STANDING: Record<string, { label: string; help: string }> = {
  supported: {
    label: "Worth a look",
    help: "Several things point this way, and more than one source agrees.",
  },
  candidate: {
    label: "Possible",
    help: "Worth considering, but only one source backs it so far.",
  },
  uncertain: { label: "Weak", help: "Very little to go on." },
  dismissed: { label: "Set aside", help: "Someone decided this was not relevant." },
};

/** Turns a signal type like "geographic_expansion" into everyday wording. */
export const ACTIVITY: Record<string, string> = {
  geographic_expansion: "Opening in new places",
  product_activity: "New products or services",
  marketing_activity: "Marketing and campaigns",
  event_activity: "Events and exhibitions",
  sponsorship_activity: "Sponsorships",
  hiring_activity: "Hiring",
  marketing_hiring: "Building a marketing team",
  partnership_activity: "Partnerships",
  community_activity: "Community work",
  digital_activity: "Website and online selling",
  growth_investment: "Growth and funding",
  leadership_change: "Leadership changes",
  recognition: "Awards and recognition",
};

/** Turns an evidence type like "new_store" into everyday wording. */
export const FINDING_KIND: Record<string, string> = {
  company_identity: "About the company",
  new_store: "New store",
  new_location: "New location",
  geographic_expansion: "Expanding",
  new_market: "New market",
  product_launch: "Product launch",
  service_launch: "New service",
  campaign: "Campaign",
  partnership: "Partnership",
  sponsorship: "Sponsorship",
  event_organization: "Hosting an event",
  event_participation: "At an event",
  hiring: "Hiring",
  marketing_hiring: "Marketing hiring",
  leadership_change: "Leadership change",
  funding: "Funding",
  investment: "Investment",
  acquisition: "Acquisition",
  award: "Award",
  community_activity: "Community",
  digital_activity: "Online",
  content_activity: "Content",
  press_activity: "In the press",
  customer_growth: "Customer growth",
  seasonal_activity: "Seasonal",
  other: "Other",
};

function lookup(
  map: Record<string, { label: string; help: string }>,
  key: string | null | undefined,
  fallback = "Unknown",
): { label: string; help: string } {
  if (!key) return { label: fallback, help: "" };
  return map[key] ?? { label: key.replace(/_/g, " "), help: "" };
}

export const plain = {
  certainty: (key?: string | null) => lookup(CERTAINTY, key, "Unclear"),
  recency: (key?: string | null) => lookup(RECENCY, key, "Date unknown"),
  strength: (key?: string | null) => lookup(STRENGTH, key, "Unrated"),
  visibility: (key?: string | null) => lookup(VISIBILITY, key, ""),
  sourceTrust: (key?: string | null) => lookup(SOURCE_TRUST, key, "Unclear source"),
  personTrust: (key?: string | null) => lookup(PERSON_TRUST, key, "Unverified"),
  opportunityStanding: (key?: string | null) => lookup(OPPORTUNITY_STANDING, key, "Possible"),
  activity: (key?: string | null) =>
    (key && ACTIVITY[key]) || (key ? key.replace(/_/g, " ") : "Activity"),
  findingKind: (key?: string | null) =>
    (key && FINDING_KIND[key]) || (key ? key.replace(/_/g, " ") : "Finding"),
};
