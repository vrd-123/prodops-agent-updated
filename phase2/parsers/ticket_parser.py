"""
ProdOps Phase 2 — Ticket Parser (v2.1 — with edge case fixes)
===============================================================
Reads a PRODOPS Jira ticket and extracts all parameters for script generation.

Built from analysis of 25+ real PRODOPS tickets.

v2.1 Fixes (from live testing against PRODOPS-3352, 3422, 3361):
  FIX 1: Fallback task type detection from summary when customfield_10370 is null.
  FIX 2: Trust description over workspace field for multi-env FHIR tickets.
  FIX 3: Extract Databricks catalog name directly from metadata table path when present.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes — Parsed ticket output
# ============================================================================

@dataclass
class S3CopyParams:
    """Parameters extracted for an S3 copy/sync task."""
    ticket_key: str
    customer: str
    source_uris: list[str] = field(default_factory=list)
    dest_uris: list[str] = field(default_factory=list)
    specific_files: list[str] = field(default_factory=list)
    copy_method: str = "sync"
    summary: str = ""
    source_env: str = ""
    dest_envs: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return bool(self.customer and self.source_uris and self.dest_uris)

    @property
    def missing_fields(self) -> list[str]:
        missing = []
        if not self.customer:
            missing.append("Customer (customfield_10081 is empty)")
        if not self.source_uris:
            missing.append("Source S3 URI (no s3:// found in description)")
        if not self.dest_uris:
            missing.append("Destination S3 URI (could not classify source vs dest)")
        return missing

    @property
    def warnings(self) -> list[str]:
        """Detect potential issues in the ticket data."""
        warns = []
        for uri in self.dest_uris:
            bucket_env = _extract_env_from_uri(uri)
            path_match = re.search(r'/sftp/\w+-(\w+)/', uri)
            if path_match and bucket_env:
                path_env = path_match.group(1)
                if path_env != bucket_env:
                    warns.append(
                        f"⚠️ Possible path/bucket mismatch: bucket env is '{bucket_env}' "
                        f"but folder path says '{path_env}' in {uri}"
                    )
        return warns


@dataclass
class FHIRCleanupParams:
    """Parameters extracted for a FHIR cleanup task."""
    ticket_key: str
    customer: str
    workspace_field: str = ""  # raw value from customfield_10684
    fhir_environments: list[str] = field(default_factory=list)
    resource_types: list[str] = field(default_factory=list)
    profile_urls: list[str] = field(default_factory=list)
    metadata_tables: list[str] = field(default_factory=list)
    # FIX 3: catalog names extracted directly from metadata table paths
    catalogs_from_tables: dict = field(default_factory=dict)  # {fhir_env: catalog_name}
    catalogs_inferred: dict = field(default_factory=dict)     # {fhir_env: catalog_name}
    fhir_server_urls: list[str] = field(default_factory=list)
    is_prod: bool = False
    summary: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return bool(
            self.customer
            and self.fhir_environments
            and (self.resource_types or self.profile_urls or self.metadata_tables)
        )

    @property
    def missing_fields(self) -> list[str]:
        missing = []
        if not self.customer:
            missing.append("Customer (customfield_10081 is empty)")
        if not self.fhir_environments:
            missing.append("FHIR environment name (e.g. gw03-vt-dev, medstar-stg)")
        if not self.resource_types and not self.profile_urls and not self.metadata_tables:
            missing.append("FHIR resource types or metadata tables to clean")
        return missing

    def get_catalog(self, fhir_env: str) -> str:
        """
        FIX 3: Get the Databricks catalog name for a FHIR environment.
        Prefers directly-extracted catalog over inferred catalog.
        """
        return (
            self.catalogs_from_tables.get(fhir_env)
            or self.catalogs_inferred.get(fhir_env)
            or _fhir_env_to_catalog(fhir_env)
        )

    def get_tables_for_env(self, fhir_env: str) -> list[str]:
        """Get metadata tables relevant to a specific FHIR environment."""
        catalog = self.get_catalog(fhir_env)
        if not catalog:
            return self.metadata_tables

        # Filter tables that match this env's catalog
        env_tables = [t for t in self.metadata_tables if catalog.rstrip("_catalog") in t.replace("_catalog.", ".")]

        # If we found env-specific tables, return those
        if env_tables:
            return env_tables

        # Otherwise return all tables (single-env ticket — all tables belong to it)
        return self.metadata_tables


# ============================================================================
# Task Type Detection
# ============================================================================

class TaskType:
    S3_COPY = "s3_copy"
    FHIR_CLEANUP = "fhir_cleanup"
    UNKNOWN = "unknown"


def detect_task_type(ticket: dict) -> str:
    """
    Detect task type from real ticket data.

    FIX 1: When customfield_10370 is null (common), falls back to
    summary keywords + description content instead of returning UNKNOWN.

    Priority order:
      1. customfield_10370 (Task Category) — if present
      2. Labels: 'data_copier_yes' → S3 Copy
      3. Summary keywords (most reliable fallback from real tickets)
      4. Description content: s3:// URIs → S3 Copy, metadata_v1 → FHIR
    """
    # --- Check customfield_10370 (Task Category) first ---
    task_category = _get_task_category(ticket)
    if task_category:
        cat_lower = task_category.lower()
        if "data cop" in cat_lower or "copy" in cat_lower:
            return TaskType.S3_COPY
        if "fhir" in cat_lower:
            return TaskType.FHIR_CLEANUP

    # --- Check labels ---
    labels = _get_labels(ticket)
    label_set = set(l.lower() for l in labels)
    if "data_copier_yes" in label_set:
        return TaskType.S3_COPY

    # --- FIX 1: Summary keyword detection (critical fallback) ---
    summary = _get_summary(ticket).lower()
    description = _get_description_text(ticket).lower()

    # FHIR summary patterns (check first — more specific)
    fhir_summary_keywords = [
        "fhir cleanup", "fhir clean", "cleanup request",
        "cleanup for", "clean up", "cleanup required",
        "fhir server", "vonkentries", "mongodb cleanup",
    ]
    if any(kw in summary for kw in fhir_summary_keywords):
        return TaskType.FHIR_CLEANUP

    # S3 copy summary patterns
    s3_summary_keywords = [
        "copy data", "copy files", "copy the files",
        "copy demo", "copy existing", "copy claims",
        "copy clinical", "copy provider", "s3 copy",
        "s3 sync", "data-lake-prd", "data-lake-dev",
    ]
    if any(kw in summary for kw in s3_summary_keywords):
        return TaskType.S3_COPY

    # --- Content-based detection (last resort) ---
    text = summary + " " + description

    has_fhir_env = bool(re.search(r'(gw\d{2}-[a-z]{2}-|medstar-|cambia\d*-)(dev|stg|uat|prd)', text))
    has_metadata = bool(re.search(r'metadata_v1\.', text))
    has_s3_uris = bool(re.search(r's3://abacus-\S+', text))

    if has_fhir_env or has_metadata:
        return TaskType.FHIR_CLEANUP
    if has_s3_uris:
        return TaskType.S3_COPY

    return TaskType.UNKNOWN


# ============================================================================
# S3 Copy Parser
# ============================================================================

def parse_s3_copy(ticket: dict, ticket_key: str) -> S3CopyParams:
    """
    Parse S3 copy parameters from a PRODOPS ticket.
    Extracts full S3 URIs directly from description — does NOT construct them.
    """
    customer = _get_customer(ticket)
    summary = _get_summary(ticket)
    description = _get_description_text(ticket)

    # Extract all S3 URIs
    s3_uris = re.findall(r's3://abacus-[^\s,\)\"\'<>\|]+', description)
    s3_uris = [uri.rstrip('.,;:)') for uri in s3_uris]
    # Deduplicate preserving order
    seen = set()
    unique_uris = []
    for uri in s3_uris:
        if uri not in seen:
            seen.add(uri)
            unique_uris.append(uri)
    s3_uris = unique_uris

    source_uris, dest_uris = _classify_s3_uris(s3_uris, summary, description)
    source_env = _extract_env_from_uri(source_uris[0]) if source_uris else ""
    dest_envs = list(set(filter(None, [_extract_env_from_uri(u) for u in dest_uris])))
    copy_method = "sync"  # default — safest (incremental, supports --dryrun)
    specific_files = _extract_file_list(description)

    return S3CopyParams(
        ticket_key=ticket_key,
        customer=customer,
        source_uris=source_uris,
        dest_uris=dest_uris,
        specific_files=specific_files,
        copy_method=copy_method,
        summary=summary,
        source_env=source_env,
        dest_envs=dest_envs,
    )


def _classify_s3_uris(
    uris: list[str], summary: str, description: str
) -> tuple[list[str], list[str]]:
    """
    Classify S3 URIs as source or destination.

    Method 1 — Explicit labels (most reliable):
      BlueKC:  "Copy from:" / "Copy to:"
      Medstar: "SOURCE:" / "TARGET"
      BCI:     "BCI Prod -" / "BCI Dev -"

    Method 2 — Environment suffix in URI:
      -prd- → source, -dev-/-stg- → destination

    Method 3 — Position fallback (first = source, rest = dest)
    """
    if not uris:
        return [], []

    source = []
    dest = []

    source_labels = ["copy from", "source", "from:", "sync from",
                     "prod -", "prd -", "prod-", "prod–"]
    dest_labels = ["copy to", "target", "to:", "dest", "destination",
                   "dev -", "stg -", "dev-", "stg-", "stage -"]

    # Method 1: Explicit labels — use nearest label to avoid misclassifying
    # multi-destination tickets where an earlier "copy from" appears in window.
    for uri in uris:
        uri_pos = description.find(uri)
        if uri_pos < 0:
            continue
        context_before = description[max(0, uri_pos - 120):uri_pos].lower()
        classification = _nearest_label_classification(
            context_before, source_labels, dest_labels
        )
        if classification == "source":
            source.append(uri)
        elif classification == "dest":
            dest.append(uri)

    if source and dest:
        return source, dest

    # Method 2: Environment suffix
    source = []
    dest = []
    for uri in uris:
        env = _extract_env_from_uri(uri)
        if env in ("prd", "prod"):
            source.append(uri)
        elif env in ("dev", "stg", "uat"):
            dest.append(uri)

    if source and dest:
        return source, dest

    # Method 3: Position fallback
    if len(uris) >= 2:
        return [uris[0]], uris[1:]

    return uris, []


def _nearest_label_classification(
    context_before: str,
    source_labels: list[str],
    dest_labels: list[str],
) -> str | None:
    """Return source/dest based on the label closest to the URI."""
    ctx = context_before.lower()
    best_source = max((ctx.rfind(lbl) for lbl in source_labels), default=-1)
    best_dest = max((ctx.rfind(lbl) for lbl in dest_labels), default=-1)
    if best_source < 0 and best_dest < 0:
        return None
    if best_source > best_dest:
        return "source"
    if best_dest > best_source:
        return "dest"
    return None


def _extract_env_from_uri(uri: str) -> str:
    """Extract environment from S3 URI."""
    uri_lower = uri.lower()
    match = re.search(r'-(prd|prod|dev|stg|uat)-\d{9,15}-', uri_lower)
    if match:
        return match.group(1)
    for env in ["prd", "prod", "stg", "dev", "uat"]:
        if f"-{env}-" in uri_lower:
            return env
    return ""


def _extract_file_list(description: str) -> list[str]:
    """Extract specific file names from ticket description."""
    files = []
    file_patterns = [
        r'(\S+\.dat)\b', r'(\S+\.csv)\b', r'(\S+\.xlsx?)\b',
        r'(\S+\.json)\b', r'(\S+\.ndjson)\b', r'(\S+\.parquet)\b',
        r'(\S+\.txt)\b', r'(\S+\.gz)\b', r'(\S+\.zip)\b',
    ]
    for pattern in file_patterns:
        matches = re.findall(pattern, description, re.IGNORECASE)
        files.extend(matches)
    return list(dict.fromkeys(files))


# ============================================================================
# FHIR Cleanup Parser
# ============================================================================

def parse_fhir_cleanup(ticket: dict, ticket_key: str) -> FHIRCleanupParams:
    """
    Parse FHIR cleanup parameters from a PRODOPS ticket.

    FIX 2: Trusts description over workspace field for environment detection.
    FIX 3: Extracts catalog name directly from metadata table paths.
    """
    customer = _get_customer(ticket)
    workspace_field = _get_workspace(ticket)
    summary = _get_summary(ticket)
    description = _get_description_text(ticket)

    # Extract FHIR environment names from description (FIX 2: primary source)
    fhir_envs = _extract_fhir_environments(description, summary)

    # FIX 2: Warn if workspace field disagrees with description
    warnings = []
    if workspace_field and fhir_envs and len(fhir_envs) > 1:
        warnings.append(
            f"⚠️ Workspace field says '{workspace_field}' but description "
            f"includes {len(fhir_envs)} environments: {', '.join(fhir_envs)}. "
            f"Generating script for ALL environments from description."
        )

    # Extract resources, profiles, metadata tables
    resource_types = _extract_fhir_resource_types(description)
    profile_urls = _extract_profile_urls(description)
    metadata_tables = _extract_metadata_tables(description)

    # FIX 3: Extract catalog names directly from metadata table paths
    catalogs_from_tables = _extract_catalogs_from_table_paths(description)

    # Also infer catalogs from FHIR env names (fallback)
    catalogs_inferred = {}
    for env in fhir_envs:
        inferred = _fhir_env_to_catalog(env)
        if inferred:
            catalogs_inferred[env] = inferred

    # FHIR server URLs (Medstar pattern)
    fhir_server_urls = re.findall(r'(https://fite\.\S+/\S+)', description)

    # Check if any env is prod
    is_prod = any("prd" in env or "prod" in env for env in fhir_envs)

    return FHIRCleanupParams(
        ticket_key=ticket_key,
        customer=customer,
        workspace_field=workspace_field,
        fhir_environments=fhir_envs,
        resource_types=resource_types,
        profile_urls=profile_urls,
        metadata_tables=metadata_tables,
        catalogs_from_tables=catalogs_from_tables,
        catalogs_inferred=catalogs_inferred,
        fhir_server_urls=fhir_server_urls,
        is_prod=is_prod,
        summary=summary,
        warnings=warnings,
    )


def _extract_fhir_environments(description: str, summary: str) -> list[str]:
    """
    Extract FHIR environment names from ticket.

    Real patterns:
      Gainwell: "Environment: gw03-vt-dev"
                "Environments: gw01-wv-dev, gw01-wv-stg"
      Medstar:  "Environment Name: medstar-stg"
      Cambia:   "Environment: cambia02-offshore"
    """
    text = description + " " + summary
    envs = []

    # Pattern 1: gw{nn}-{state}-{env}
    gw_matches = re.findall(r'(gw\d{2}-[a-z]{2,4}-(?:dev|stg|uat|prd))', text, re.IGNORECASE)
    envs.extend([m.lower() for m in gw_matches])

    # Pattern 2: medstar-{env}
    ms_matches = re.findall(r'(medstar-(?:dev|stg|uat|prd))', text, re.IGNORECASE)
    envs.extend([m.lower() for m in ms_matches])

    # Pattern 3: cambia{n}-{env}
    cam_matches = re.findall(r'(cambia\d*-[a-z]+)', text, re.IGNORECASE)
    envs.extend([m.lower() for m in cam_matches])

    # Pattern 4: Loose state-env (Gainwell fallback)
    if not envs:
        loose_match = re.findall(
            r'\b(VT|CT|OK|WV|IN|KS|NV)\s*[-]?\s*(DEV|STG|STAGE|UAT|PRD|PROD)\b',
            text, re.IGNORECASE
        )
        env_map = {"stage": "stg", "prod": "prd"}
        for state, env in loose_match:
            env_lower = env_map.get(env.lower(), env.lower())
            envs.append(f"gw??-{state.lower()}-{env_lower}")

    # Deduplicate preserving order
    seen = set()
    unique = []
    for e in envs:
        if e not in seen:
            seen.add(e)
            unique.append(e)
    return unique


def _extract_fhir_resource_types(description: str) -> list[str]:
    """Extract FHIR resource type names from ticket description."""
    known_types = [
        "Practitioner", "PractitionerRole", "InsurancePlan",
        "Organization", "OrganizationAffiliation", "Network",
        "Location", "Bundle", "Patient", "Coverage",
        "ExplanationOfBenefit", "Encounter", "Condition",
        "Procedure", "Observation", "MedicationRequest",
        "MedicationDispense", "MedicationKnowledge",
        "AllergyIntolerance", "Immunization",
        "DiagnosticReport", "Claim", "ClaimResponse",
        "Consent", "DocumentReference", "Endpoint",
        "HealthcareService", "Group", "RelatedPerson",
        "CarePlan", "Goal", "Medication", "Basic",
    ]
    found = []
    for fhir_type in known_types:
        if re.search(rf'\b{fhir_type}\b', description):
            found.append(fhir_type)
    # Normalize "Insurance Plan" (space) to "InsurancePlan"
    if "Insurance Plan" in description and "InsurancePlan" not in found:
        found.append("InsurancePlan")
    return found


def _extract_profile_urls(description: str) -> list[str]:
    """Extract FHIR profile URLs from ticket description."""
    profiles = []

    # Pattern: Resource?_profile=URL
    matches = re.findall(r"(\w+\?_profile=https?://\S+)", description)
    profiles.extend(matches)

    # Pattern: 'Resource' URL
    matches = re.findall(r"'(\w+)'\s+(https?://hl7\.org/fhir/\S+)", description)
    for resource, url in matches:
        profiles.append(f"{resource}?_profile={url}")

    # Standalone hl7 profile URLs
    if not profiles:
        standalone = re.findall(r'(https?://hl7\.org/fhir/[^\s,\)]+)', description)
        profiles.extend(standalone)

    return list(dict.fromkeys(profiles))


def _extract_metadata_tables(description: str) -> list[str]:
    """
    Extract Databricks metadata table names.

    Handles both formats seen in real tickets:
      Short:  metadata_v1.reference_pvd_resourcestatus
      Full:   gw01_wvdev_catalog.metadata_v1.reference_formulary
    """
    # Full path (with catalog prefix)
    full_tables = re.findall(
        r'(\w+_catalog\.metadata_v1\.\w+)',
        description, re.IGNORECASE
    )
    if full_tables:
        return list(dict.fromkeys(full_tables))

    # Short path (no catalog prefix)
    short_tables = re.findall(
        r'(metadata_v1\.\w+)',
        description, re.IGNORECASE
    )
    return list(dict.fromkeys(short_tables))


def _extract_catalogs_from_table_paths(description: str) -> dict:
    """
    FIX 3: Extract catalog names directly from full metadata table paths.

    Real example from PRODOPS-3361:
      "gw01_wvdev_catalog.metadata_v1.reference_formulary" → gw01_wvdev_catalog
      "gw01_wvstg_catalog.metadata_v1.reference_formulary" → gw01_wvstg_catalog

    Returns dict mapping FHIR env → catalog name.
    """
    catalog_matches = re.findall(
        r'(\w+_catalog)\.metadata_v1\.',
        description, re.IGNORECASE
    )
    catalogs = list(dict.fromkeys(catalog_matches))

    # Map each catalog back to its FHIR environment
    result = {}
    for cat in catalogs:
        fhir_env = _catalog_to_fhir_env(cat)
        if fhir_env:
            result[fhir_env] = cat

    return result


def _catalog_to_fhir_env(catalog: str) -> str:
    """
    Reverse-map a Databricks catalog name to a FHIR environment name.

    gw01_wvdev_catalog → gw01-wv-dev
    gw03_ctstg_catalog → gw03-ct-stg
    medstar_stg_catalog → medstar-stg
    """
    cat = catalog.lower().replace("_catalog", "")

    # Gainwell pattern: gw01_wvdev → gw01-wv-dev
    gw_match = re.match(r'(gw\d{2})_([a-z]{2})(dev|stg|uat|prd)$', cat)
    if gw_match:
        return f"{gw_match.group(1)}-{gw_match.group(2)}-{gw_match.group(3)}"

    # Medstar/Cambia pattern: medstar_stg → medstar-stg
    other_match = re.match(r'(\w+?)_(dev|stg|uat|prd)$', cat)
    if other_match:
        return f"{other_match.group(1)}-{other_match.group(2)}"

    return ""


def _fhir_env_to_catalog(fhir_env: str) -> str:
    """
    Infer Databricks catalog from FHIR env name (fallback when not in table path).

    gw03-vt-dev → gw03_vtdev_catalog
    medstar-stg → medstar_stg_catalog
    """
    if not fhir_env or "??" in fhir_env:
        return ""

    parts = fhir_env.split("-")
    if len(parts) == 3:
        # Gainwell: gw03-ct-stg → gw03_ctstg_catalog
        return f"{parts[0]}_{parts[1]}{parts[2]}_catalog"
    elif len(parts) == 2:
        # Medstar/Cambia: medstar-stg → medstar_stg_catalog
        return f"{parts[0]}_{parts[1]}_catalog"
    return fhir_env.replace("-", "_") + "_catalog"


# ============================================================================
# Jira Field Extractors
# ============================================================================

def _get_customer(ticket: dict) -> str:
    """
    Extract customer name from customfield_10081.
    Real format: list of dicts [{'value': 'BCI', 'id': '11865'}]
    """
    fields = ticket.get("fields", {})
    cf = fields.get("customfield_10081")
    if isinstance(cf, list) and cf:
        first = cf[0]
        if isinstance(first, dict):
            return first.get("value", "") or first.get("name", "")
        return str(first)
    if isinstance(cf, dict):
        return cf.get("value", "") or cf.get("name", "")
    if isinstance(cf, str):
        return cf
    return ""


def _get_workspace(ticket: dict) -> str:
    """Extract workspace from customfield_10684."""
    fields = ticket.get("fields", {})
    cf = fields.get("customfield_10684")
    if isinstance(cf, list) and cf:
        first = cf[0]
        if isinstance(first, dict):
            return first.get("value", "") or first.get("name", "")
        return str(first)
    if isinstance(cf, dict):
        return cf.get("value", "") or cf.get("name", "")
    if isinstance(cf, str):
        return cf
    return ""


def _get_task_category(ticket: dict) -> str:
    """
    Extract task category from customfield_10370.
    FIX 1: Returns empty string when null (common), so caller can fall through.
    """
    fields = ticket.get("fields", {})
    cf = fields.get("customfield_10370")
    if cf is None:
        return ""
    if isinstance(cf, list) and cf:
        first = cf[0]
        if isinstance(first, dict):
            return first.get("value", "") or first.get("name", "")
        return str(first)
    if isinstance(cf, dict):
        return cf.get("value", "") or cf.get("name", "")
    if isinstance(cf, str):
        return cf
    return ""


def _get_labels(ticket: dict) -> list[str]:
    """Extract labels."""
    fields = ticket.get("fields", {})
    labels = fields.get("labels", [])
    return [str(l) for l in labels] if isinstance(labels, list) else []


def _get_summary(ticket: dict) -> str:
    """Extract ticket summary."""
    return ticket.get("fields", {}).get("summary", "") or ""


def _get_description_text(ticket: dict) -> str:
    """Extract description as plain text. Handles both string and ADF."""
    desc = ticket.get("fields", {}).get("description")
    if desc is None:
        return ""
    if isinstance(desc, str):
        return desc
    if isinstance(desc, dict) and "content" in desc:
        return _adf_to_text(desc)
    return str(desc)


def _adf_to_text(adf_node: dict) -> str:
    """Recursively convert Atlassian Document Format to plain text."""
    if not isinstance(adf_node, dict):
        return ""
    node_type = adf_node.get("type", "")
    if node_type == "text":
        return adf_node.get("text", "")
    if node_type == "hardBreak":
        return "\n"
    parts = []
    for child in adf_node.get("content", []):
        parts.append(_adf_to_text(child))
    joined = "".join(parts)
    if node_type in ("paragraph", "heading", "codeBlock", "blockquote"):
        return joined + "\n"
    if node_type == "listItem":
        return "- " + joined + "\n"
    return joined
