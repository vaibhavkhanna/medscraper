"""
JSON-LD / Schema.org parser for doctor extraction.

Hospital websites increasingly embed structured data in <script type="application/ld+json">
tags. This module parses those blocks and maps them to ExtractedDoctor records.

Supported schema.org types:
  - Person
  - Physician
  - MedicalBusiness  (clinic/hospital with staff members)
  - Hospital         (with employees/staff)
  - MedicalOrganization
  - ItemList / ListItem (doctor directory pages)
"""

import json
import re
from typing import Any, Optional
from bs4 import BeautifulSoup

# Import shared helpers from extractor — avoid circular imports by using lazy import
# All heavy lifting is done here; extractor just calls extract_jsonld_from_page()


# ── Schema types that directly represent a person/provider ────────────────────
PERSON_TYPES = {
    "person", "physician", "medicalprofessional",
    "medicalpractitioner", "healthcareprovider",
}

# ── Schema types that are organizations containing people ─────────────────────
ORG_TYPES = {
    "medicalbusiness", "hospital", "medicalorganization",
    "medicalclinic", "clinic", "medicalspecialty",
    "healthclub", "dentist", "pharmacy",
}

# ── Keys within a Person node that may hold contact info ──────────────────────
# Maps schema.org property → our field name
EMAIL_KEYS = ["email", "contactEmail"]
PHONE_KEYS = ["telephone", "faxNumber", "phone", "contactPoint"]
LINKEDIN_KEYS = ["sameAs", "url", "mainEntityOfPage"]
SPECIALTY_KEYS = ["medicalSpecialty", "specialty", "hasCredential",
                  "knowsAbout", "jobTitle", "description"]
NPI_KEYS = ["identifier", "npi", "medicalCode"]


def _get_type(node: dict) -> str:
    """Normalise @type to lowercase string."""
    t = node.get("@type", "")
    if isinstance(t, list):
        t = t[0] if t else ""
    return t.lower().replace("schema:", "")


def _coerce_str(val: Any) -> str:
    """Safely coerce any value to a plain string."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, list):
        return " ".join(_coerce_str(v) for v in val if v).strip()
    if isinstance(val, dict):
        # e.g. {"@type": "Text", "name": "Cardiology"}
        return _coerce_str(val.get("name") or val.get("@value") or "")
    return str(val).strip()


def _extract_emails_from_node(node: dict) -> list[str]:
    emails = []
    for key in EMAIL_KEYS:
        val = node.get(key, "")
        raw = _coerce_str(val)
        if "@" in raw:
            # Handle mailto: prefix
            raw = raw.replace("mailto:", "").strip()
            if raw and raw not in emails:
                emails.append(raw)
    # Also scan contactPoint array
    cp = node.get("contactPoint", [])
    if isinstance(cp, dict):
        cp = [cp]
    for point in cp if isinstance(cp, list) else []:
        e = _coerce_str(point.get("email", ""))
        if "@" in e and e not in emails:
            emails.append(e.replace("mailto:", "").strip())
    return emails[:2]


def _extract_phones_from_node(node: dict) -> list[str]:
    phones = []
    for key in ["telephone", "faxNumber"]:
        val = _coerce_str(node.get(key, ""))
        if val and val not in phones:
            phones.append(val)
    # contactPoint
    cp = node.get("contactPoint", [])
    if isinstance(cp, dict):
        cp = [cp]
    for point in cp if isinstance(cp, list) else []:
        t = _coerce_str(point.get("telephone", ""))
        if t and t not in phones:
            phones.append(t)
    return phones[:2]


def _extract_linkedin(node: dict) -> str:
    for key in LINKEDIN_KEYS:
        val = node.get(key, "")
        if isinstance(val, list):
            for v in val:
                s = _coerce_str(v)
                if "linkedin.com/in/" in s.lower():
                    return s
        else:
            s = _coerce_str(val)
            if "linkedin.com/in/" in s.lower():
                return s
    return ""


def _extract_specialty(node: dict) -> str:
    """Pull specialty from various schema fields."""
    for key in SPECIALTY_KEYS:
        val = node.get(key, "")
        if not val:
            continue
        raw = _coerce_str(val)
        if raw:
            # Strip schema.org URIs like "http://schema.org/Cardiology"
            raw = raw.rstrip("/").split("/")[-1]
            # CamelCase → words: "FamilyMedicine" → "Family Medicine"
            raw = re.sub(r"([a-z])([A-Z])", r"\1 \2", raw)
            return raw.strip()
    return ""


def _extract_npi(node: dict) -> str:
    """Look for NPI in identifier fields."""
    identifiers = node.get("identifier", [])
    if isinstance(identifiers, dict):
        identifiers = [identifiers]
    if isinstance(identifiers, str):
        # bare string — check if it looks like a 10-digit NPI
        if re.fullmatch(r"\d{10}", identifiers.strip()):
            return identifiers.strip()
        return ""
    for ident in identifiers if isinstance(identifiers, list) else []:
        prop_id = _coerce_str(ident.get("propertyID", "")).lower()
        value = _coerce_str(ident.get("value", "") or ident.get("@value", ""))
        if "npi" in prop_id and re.fullmatch(r"\d{10}", value):
            return value
        # Sometimes NPI is just a bare 10-digit value
        if re.fullmatch(r"\d{10}", value):
            return value
    # Direct npi key
    npi_direct = _coerce_str(node.get("npi", ""))
    if re.fullmatch(r"\d{10}", npi_direct):
        return npi_direct
    return ""


def _parse_person_node(node: dict, url: str) -> Optional[dict]:
    """
    Convert a schema.org Person/Physician node into a field dict.
    Returns None if we can't extract a usable name.
    """
    from extractor import split_name, extract_title, detect_contact_type, SPECIALTY_PATTERN

    first_name = _coerce_str(node.get("givenName", ""))
    last_name = _coerce_str(node.get("familyName", ""))

    # Fall back to full "name" field
    if not first_name and not last_name:
        full = _coerce_str(node.get("name", ""))
        if full:
            first_name, last_name = split_name(full)

    if not first_name and not last_name:
        return None

    # Title / credential
    job_title = _coerce_str(node.get("jobTitle", ""))
    honor_prefix = _coerce_str(node.get("honorificPrefix", ""))
    honor_suffix = _coerce_str(node.get("honorificSuffix", ""))
    title_text = f"{honor_prefix} {job_title} {honor_suffix}".strip()
    title = extract_title(title_text) or extract_title(f"{first_name} {last_name} {title_text}")

    # Specialty
    specialty = _extract_specialty(node)
    # Validate against our known list
    if specialty:
        m = SPECIALTY_PATTERN.search(specialty)
        specialty = m.group(0) if m else specialty

    # Emails & phones
    emails = _extract_emails_from_node(node)
    phones = _extract_phones_from_node(node)

    # LinkedIn
    linkedin = _extract_linkedin(node)

    # NPI
    npi = _extract_npi(node)

    # Contact type
    schema_type = _get_type(node)
    if schema_type in ("physician", "medicalprofessional", "healthcareprovider"):
        contact_type = "Doctor"
    else:
        combined = f"{title_text} {specialty} {first_name} {last_name}"
        contact_type = detect_contact_type(combined, title)

    return {
        "first_name": first_name,
        "last_name": last_name,
        "title": title,
        "specialty": specialty,
        "email1": emails[0] if len(emails) > 0 else "",
        "email2": emails[1] if len(emails) > 1 else "",
        "phone1": phones[0] if len(phones) > 0 else "",
        "phone2": phones[1] if len(phones) > 1 else "",
        "npi": npi,
        "linkedin": linkedin,
        "contact_type": contact_type,
        "source_url": url,
    }


def _collect_person_nodes(data: Any) -> list[dict]:
    """
    Recursively walk a JSON-LD graph and collect all person-like nodes.
    Handles:
      - Single object
      - @graph array
      - Arrays of objects
      - Nested employee / member / subjectOf arrays inside org nodes
    """
    nodes = []

    if isinstance(data, list):
        for item in data:
            nodes.extend(_collect_person_nodes(item))
        return nodes

    if not isinstance(data, dict):
        return nodes

    schema_type = _get_type(data)

    # Direct person node
    if schema_type in PERSON_TYPES:
        nodes.append(data)
        return nodes

    # @graph — flat list of mixed types
    if "@graph" in data:
        for item in data["@graph"]:
            nodes.extend(_collect_person_nodes(item))

    # Organisation node — look for nested staff
    if schema_type in ORG_TYPES or not schema_type:
        for key in ("employee", "member", "staff", "subjectOf",
                    "medicalStaff", "founder", "alumniOf", "performer"):
            nested = data.get(key, [])
            if isinstance(nested, dict):
                nested = [nested]
            if isinstance(nested, list):
                for item in nested:
                    nodes.extend(_collect_person_nodes(item))

    # ItemList — doctor directory pages often use this
    if schema_type in ("itemlist", "breadcrumblist"):
        items = data.get("itemListElement", [])
        if isinstance(items, list):
            for item in items:
                # ListItem wraps the actual object in "item"
                inner = item.get("item", item)
                nodes.extend(_collect_person_nodes(inner))

    return nodes


def extract_jsonld_from_page(html: str, url: str) -> list:
    """
    Main entry point. Parses all JSON-LD blocks in the page HTML,
    collects person nodes, and returns a list of ExtractedDoctor objects.
    """
    from extractor import ExtractedDoctor

    soup = BeautifulSoup(html, "lxml")
    script_tags = soup.find_all("script", type="application/ld+json")

    if not script_tags:
        return []

    person_nodes = []

    for tag in script_tags:
        raw = tag.string or tag.get_text()
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to salvage malformed JSON by stripping comments/trailing commas
            try:
                cleaned = re.sub(r"//.*?$", "", raw, flags=re.MULTILINE)
                cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
                data = json.loads(cleaned)
            except Exception:
                continue

        found = _collect_person_nodes(data)
        person_nodes.extend(found)

    if not person_nodes:
        return []

    doctors = []
    seen: set[str] = set()

    for node in person_nodes:
        fields = _parse_person_node(node, url)
        if not fields:
            continue

        doc = ExtractedDoctor(**fields)
        if not doc.is_valid():
            continue

        fp = doc.fingerprint()
        if fp not in seen:
            seen.add(fp)
            doctors.append(doc)

    return doctors
