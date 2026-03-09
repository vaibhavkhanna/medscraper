import re
from dataclasses import dataclass, field
from typing import Optional
from bs4 import BeautifulSoup

# ── Medical specialties keyword list ──────────────────────────────────────────
SPECIALTIES = [
    "Cardiology", "Cardiologist", "Neurology", "Neurologist", "Oncology",
    "Oncologist", "Orthopedics", "Orthopedic", "Pediatrics", "Pediatrician",
    "Dermatology", "Dermatologist", "Psychiatry", "Psychiatrist", "Radiology",
    "Radiologist", "Anesthesiology", "Anesthesiologist", "Ophthalmology",
    "Ophthalmologist", "Gynecology", "Gynecologist", "Obstetrics", "Obstetrician",
    "Urology", "Urologist", "Gastroenterology", "Gastroenterologist",
    "Endocrinology", "Endocrinologist", "Nephrology", "Nephrologist",
    "Pulmonology", "Pulmonologist", "Rheumatology", "Rheumatologist",
    "Hematology", "Hematologist", "Infectious Disease", "Internal Medicine",
    "Family Medicine", "General Practice", "General Practitioner", "GP",
    "Emergency Medicine", "Surgery", "Surgeon", "Plastic Surgery",
    "Plastic Surgeon", "Vascular Surgery", "Neurosurgery", "Neurosurgeon",
    "ENT", "Otolaryngology", "Otolaryngologist", "Pathology", "Pathologist",
    "Neonatology", "Neonatologist", "Geriatrics", "Geriatrician",
    "Sports Medicine", "Pain Management", "Palliative Care", "Immunology",
    "Allergist", "Allergy", "Physical Medicine", "Rehabilitation",
    "Physiotherapy", "Physiotherapist", "Dentistry", "Dentist",
    "Orthodontics", "Orthodontist", "Oral Surgery", "Nutrition",
    "Nutritionist", "Dietitian", "Psychology", "Psychologist",
    "Hospitalist", "Intensivist", "Critical Care", "Trauma Surgery",
    "Colorectal Surgery", "Thoracic Surgery", "Bariatric Surgery",
    "Reproductive Medicine", "Fertility", "Maternal-Fetal Medicine",
    "Wound Care", "Hyperbaric Medicine", "Sleep Medicine",
]

SPECIALTY_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in SPECIALTIES) + r")\b",
    re.IGNORECASE,
)

# Medical credentials/titles
CREDENTIAL_TITLES = [
    "MD", "M.D.", "DO", "D.O.", "MBBS", "MBChB", "PharmD", "DDS", "DMD",
    "DVM", "PhD", "MS", "FACS", "FACP", "FACOG", "FAAP", "FAAN", "NP",
    "PA", "PA-C", "RN", "ARNP", "CRNA", "CNM", "CNS", "FNP", "GNP",
]

TITLE_PREFIX_RE = re.compile(
    r"\b(Dr\.?|Prof\.?|Doctor|Professor)\b",
    re.IGNORECASE,
)

NAME_TITLE_RE = re.compile(
    r"\b(Dr\.?|Prof\.?|Doctor|Professor)\s+"
    r"([A-Z][a-z]+(?:[\s\-][A-Z][a-z]+){0,3})",
)

CREDENTIAL_SUFFIX_RE = re.compile(
    r"\b([A-Z][a-z]+(?:[\s\-][A-Z][a-z]+){0,3})"
    r",?\s*(" + "|".join(re.escape(c) for c in CREDENTIAL_TITLES) + r")"
    r"\b"
)

EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]?)?"
    r"(?:\(?\d{2,4}\)?[\s\-.]?)"
    r"\d{3,4}[\s\-.]?\d{3,5}"
)

LINKEDIN_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+/?",
    re.IGNORECASE,
)

NPI_RE = re.compile(r"\bNPI[:\s#]*(\d{10})\b", re.IGNORECASE)

STAFF_SIGNALS = re.compile(
    r"\b(nurse|coordinator|administrator|receptionist|assistant|"
    r"technician|therapist|counselor|social worker|manager|director|"
    r"secretary|billing|scheduler|front desk)\b",
    re.IGNORECASE,
)

GENERIC_EMAILS = {"noreply", "info@", "contact@", "admin@", "support@",
                  "example", "webmaster@", "hello@", "office@"}


@dataclass
class ExtractedDoctor:
    first_name: str = ""
    last_name: str = ""
    title: str = ""
    specialty: str = ""
    email1: str = ""
    email2: str = ""
    phone1: str = ""
    phone2: str = ""
    npi: str = ""
    linkedin: str = ""
    contact_type: str = ""
    source_url: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def fingerprint(self) -> str:
        name = re.sub(r"\s+", " ", self.full_name.lower().strip())
        name = re.sub(r"^(dr\.?|prof\.?|doctor|professor)\s+", "", name)
        name = re.sub(r"[^\w\s]", "", name).strip()
        email = self.email1.lower().strip()
        phone = re.sub(r"\D", "", self.phone1)
        return f"{name}|{email}|{phone}"

    def name_fingerprint(self) -> str:
        """Name-only fingerprint to catch duplicates that differ only in contact info."""
        name = re.sub(r"\s+", " ", self.full_name.lower().strip())
        name = re.sub(r"^(dr\.?|prof\.?|doctor|professor)\s+", "", name)
        name = re.sub(r"[^\w\s]", "", name).strip()
        return name

    def is_valid(self) -> bool:
        return bool(self.first_name or self.last_name) and \
               bool(self.email1 or self.phone1 or self.specialty)


def split_name(full: str) -> tuple[str, str]:
    full = TITLE_PREFIX_RE.sub("", full).strip(" ,.")
    parts = full.split()
    if len(parts) == 0:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]


def extract_title(text: str) -> str:
    for cred in CREDENTIAL_TITLES:
        pattern = re.compile(r"\b" + re.escape(cred) + r"\b", re.IGNORECASE)
        if pattern.search(text):
            return cred
    return ""


def clean_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 7 or len(digits) > 15:
        return ""
    return raw.strip()


def is_generic_email(email: str) -> bool:
    return any(g in email.lower() for g in GENERIC_EMAILS)


def extract_emails(text: str) -> list[str]:
    found = EMAIL_RE.findall(text)
    personal = [e for e in found if not is_generic_email(e)]
    generic = [e for e in found if is_generic_email(e)]
    return (personal + generic)[:2]


def extract_phones(text: str) -> list[str]:
    raw_phones = PHONE_RE.findall(text)
    results = []
    for p in raw_phones:
        c = clean_phone(p)
        if c and c not in results:
            results.append(c)
        if len(results) == 2:
            break
    return results


def detect_contact_type(text: str, title: str) -> str:
    if STAFF_SIGNALS.search(text) and not NAME_TITLE_RE.search(text):
        return "Staff"
    if title or NAME_TITLE_RE.search(text) or CREDENTIAL_SUFFIX_RE.search(text):
        return "Doctor"
    if SPECIALTY_PATTERN.search(text):
        return "Doctor"
    return "Staff"


def _merge_doctor(existing: ExtractedDoctor, new: ExtractedDoctor) -> None:
    """Merge contact info from `new` into `existing` to fill any gaps."""
    if not existing.email1 and new.email1:
        existing.email1 = new.email1
    if not existing.email2 and new.email2 and new.email2 != existing.email1:
        existing.email2 = new.email2
    if not existing.phone1 and new.phone1:
        existing.phone1 = new.phone1
    if not existing.phone2 and new.phone2 and new.phone2 != existing.phone1:
        existing.phone2 = new.phone2
    if not existing.npi and new.npi:
        existing.npi = new.npi
    if not existing.linkedin and new.linkedin:
        existing.linkedin = new.linkedin
    if not existing.specialty and new.specialty:
        existing.specialty = new.specialty
    if not existing.title and new.title:
        existing.title = new.title


def extract_from_page(html: str, url: str) -> list[ExtractedDoctor]:
    from jsonld_parser import extract_jsonld_from_page

    # Two-level dedup:
    #   seen_fp    — exact fingerprint (name|email|phone): prevents identical rows
    #   seen_name  — name-only fingerprint: merges contact info for same person
    seen_fp: set[str] = set()
    seen_name: dict[str, ExtractedDoctor] = {}  # name_fp -> doctor record
    doctors: list[ExtractedDoctor] = []

    def _add(doc: ExtractedDoctor) -> None:
        """Add doc with dedup; merges contact info if name already seen."""
        fp = doc.fingerprint()
        name_fp = doc.name_fingerprint()
        if not name_fp:
            return
        if name_fp in seen_name:
            # Same person — merge any new contact info into the existing record
            _merge_doctor(seen_name[name_fp], doc)
        elif fp not in seen_fp:
            seen_fp.add(fp)
            seen_name[name_fp] = doc
            doctors.append(doc)

    # ── Strategy 1: JSON-LD structured data (highest accuracy) ───────────────
    jsonld_docs = extract_jsonld_from_page(html, url)
    for doc in jsonld_docs:
        _add(doc)

    # ── Strategy 2: Block-level HTML extraction ───────────────────────────────
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    candidate_blocks = _find_doctor_blocks(soup)
    for block in candidate_blocks:
        text = block.get_text(separator=" ", strip=True)
        block_html = str(block)
        doc = _extract_from_text_block(text, block_html, url)
        if doc and doc.is_valid():
            _add(doc)

    # ── Strategy 3: Full-page text scan (last resort) ─────────────────────────
    if not doctors:
        full_text = soup.get_text(separator="\n", strip=True)
        full_html = str(soup)
        docs = _scan_full_text(full_text, full_html, url)
        for doc in docs:
            _add(doc)

    return doctors


def _find_doctor_blocks(soup: BeautifulSoup):
    blocks = []

    selectors = [
        {"class": re.compile(r"doctor|physician|provider|staff|team|profile|bio|card|member", re.I)},
        {"id": re.compile(r"doctor|physician|provider|staff|team|profile|bio|card|member", re.I)},
    ]

    for sel in selectors:
        for tag in soup.find_all(True, attrs=sel):
            blocks.append(tag)

    for tag in soup.find_all(["article", "li", "div", "section"]):
        text = tag.get_text()
        if NAME_TITLE_RE.search(text) or CREDENTIAL_SUFFIX_RE.search(text):
            if 20 < len(text) < 2000:
                blocks.append(tag)

    # Deduplicate by object identity
    seen_ids = set()
    unique = []
    for b in blocks:
        bid = id(b)
        if bid not in seen_ids:
            seen_ids.add(bid)
            unique.append(b)

    # Remove blocks that are ancestors of other blocks in the list
    # to prevent extracting the same doctor from both a container and its child
    block_set = set(id(b) for b in unique)
    non_nested = []
    for b in unique:
        is_ancestor = False
        for other in unique:
            if id(other) == id(b):
                continue
            # Check if b is an ancestor (parent) of other
            for parent in other.parents:
                if id(parent) == id(b):
                    is_ancestor = True
                    break
            if is_ancestor:
                break
        if not is_ancestor:
            non_nested.append(b)

    return non_nested


def _extract_from_text_block(text: str, html: str, url: str) -> Optional[ExtractedDoctor]:
    first_name = ""
    last_name = ""

    m = NAME_TITLE_RE.search(text)
    if m:
        first_name, last_name = split_name(m.group(2))

    if not first_name:
        m = CREDENTIAL_SUFFIX_RE.search(text)
        if m:
            first_name, last_name = split_name(m.group(1))

    if not first_name and not last_name:
        return None

    title = extract_title(text)

    specialty = ""
    m = SPECIALTY_PATTERN.search(text)
    if m:
        specialty = m.group(0).strip()

    emails = extract_emails(text)
    email1 = emails[0] if len(emails) > 0 else ""
    email2 = emails[1] if len(emails) > 1 else ""

    phones = extract_phones(text)
    phone1 = phones[0] if len(phones) > 0 else ""
    phone2 = phones[1] if len(phones) > 1 else ""

    linkedin = ""
    li_m = LINKEDIN_RE.search(html)
    if li_m:
        linkedin = li_m.group(0)

    npi = ""
    npi_m = NPI_RE.search(text)
    if npi_m:
        npi = npi_m.group(1)

    contact_type = detect_contact_type(text, title)

    return ExtractedDoctor(
        first_name=first_name,
        last_name=last_name,
        title=title,
        specialty=specialty,
        email1=email1,
        email2=email2,
        phone1=phone1,
        phone2=phone2,
        npi=npi,
        linkedin=linkedin,
        contact_type=contact_type,
        source_url=url,
    )


def _scan_full_text(text: str, html: str, url: str) -> list[ExtractedDoctor]:
    results = []
    lines = text.split("\n")
    current: dict = {}

    def flush():
        if current.get("first_name") or current.get("last_name"):
            doc = ExtractedDoctor(**current, source_url=url)
            if doc.is_valid():
                results.append(doc)
        current.clear()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        name_m = NAME_TITLE_RE.search(line)
        cred_m = CREDENTIAL_SUFFIX_RE.search(line)

        if name_m or cred_m:
            if current.get("first_name") or current.get("last_name"):
                flush()
            raw_name = name_m.group(2) if name_m else cred_m.group(1)
            fn, ln = split_name(raw_name)
            current["first_name"] = fn
            current["last_name"] = ln
            current["title"] = extract_title(line)
            current.setdefault("specialty", "")
            current.setdefault("email1", "")
            current.setdefault("email2", "")
            current.setdefault("phone1", "")
            current.setdefault("phone2", "")
            current.setdefault("npi", "")
            current.setdefault("linkedin", "")
            current.setdefault("contact_type", "")

        if current:
            if not current.get("email1") or not current.get("email2"):
                emails = extract_emails(line)
                if emails:
                    if not current.get("email1"):
                        current["email1"] = emails[0]
                        if len(emails) > 1:
                            current["email2"] = emails[1]
                    elif not current.get("email2"):
                        current["email2"] = emails[0]

            if not current.get("phone1") or not current.get("phone2"):
                phones = extract_phones(line)
                if phones:
                    if not current.get("phone1"):
                        current["phone1"] = phones[0]
                        if len(phones) > 1:
                            current["phone2"] = phones[1]
                    elif not current.get("phone2"):
                        current["phone2"] = phones[0]

            if not current.get("specialty"):
                m = SPECIALTY_PATTERN.search(line)
                if m:
                    current["specialty"] = m.group(0)

            if not current.get("npi"):
                npi_m = NPI_RE.search(line)
                if npi_m:
                    current["npi"] = npi_m.group(1)

    flush()

    # Assign LinkedIn URLs across results
    li_matches = LINKEDIN_RE.findall(html)
    for i, doc in enumerate(results):
        if not doc.linkedin and i < len(li_matches):
            doc.linkedin = li_matches[i]

    for doc in results:
        if not doc.contact_type:
            doc.contact_type = detect_contact_type(
                f"{doc.full_name} {doc.specialty} {doc.title}", doc.title
            )

    return results
