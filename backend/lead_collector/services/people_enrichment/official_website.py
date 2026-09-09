import re
from html.parser import HTMLParser
from urllib.parse import urlparse

from lead_collector.services.enrichment.base import EnrichmentError
from lead_collector.services.enrichment.hotel_website import (
    BUSINESS_EMAIL_PREFIXES,
    EMAIL_PATTERN,
    MAX_PAGES,
    SALES_NEGATIVE_MARKERS,
    _business_email,
    _discover_pages,
    _extract_contacts,
    _fetch_html,
    _page_category,
)
from lead_collector.services.enrichment.website_discovery import discover_official_website

from .base import PeopleEnrichmentError, PeopleEnrichmentProvider


SOURCE = 'Official Website'
MAX_CONTACTS = 10
PAGE_PRIORITY = ('team', 'leadership', 'management', 'sales', 'press', 'about', 'contact')
HIGH_CONFIDENCE_PAGES = {'team', 'leadership', 'management'}

TITLE_PATTERNS = (
    ('it_leadership', 'Director of Information Technology', r'Director of Information Technology'),
    ('it_leadership', 'Head of Information Technology', r'Head of Information Technology'),
    ('it_leadership', 'IT Director', r'IT Director'),
    ('it_leadership', 'Director of IT', r'Director of IT'),
    ('it_leadership', 'Head of IT', r'Head of IT'),
    ('it_management', 'IT Infrastructure Manager', r'IT Infrastructure Manager'),
    ('it_management', 'Infrastructure Manager', r'Infrastructure Manager'),
    ('it_management', 'Information Technology Manager', r'Information Technology Manager'),
    ('it_management', 'IT Manager', r'IT Manager'),
    ('executive', 'Chief Information Officer', r'Chief Information Officer'),
    ('executive', 'Chief Technology Officer', r'Chief Technology Officer'),
    ('executive', 'CIO', r'CIO'),
    ('executive', 'CTO', r'CTO'),
    ('general_manager', 'Hotel General Manager', r'Hotel General Manager'),
    ('general_manager', 'General Manager', r'General Manager'),
    ('operations', 'Director of Operations', r'Director of Operations'),
    ('operations', 'Operations Director', r'Operations Director'),
    ('operations', 'Head of Operations', r'Head of Operations'),
    ('operations', 'Operations Manager', r'Operations Manager'),
    ('sales', 'Director of Sales', r'Director of Sales'),
    ('sales', 'Sales Director', r'Sales Director'),
    ('sales', 'Head of Sales', r'Head of Sales'),
    ('sales', 'Corporate Sales Manager', r'Corporate Sales Manager'),
    ('sales', 'Sales Manager', r'Sales Manager'),
    ('sales', 'Sales Executive', r'Sales Executive'),
)
TITLE_EXPRESSION = '|'.join(f'(?:{pattern})' for _, _, pattern in TITLE_PATTERNS)
NAME_EXPRESSION = (
    r"[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'.-]+"
    r"(?:\s+[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'.-]+){1,3}"
)
PERSON_PATTERNS = (
    re.compile(
        rf'(?P<name>{NAME_EXPRESSION})\s*(?:—|–|-|,|\|)\s*'
        rf'(?P<title>{TITLE_EXPRESSION})',
        re.IGNORECASE,
    ),
    re.compile(
        rf'(?P<title>{TITLE_EXPRESSION})\s*:\s*(?P<name>{NAME_EXPRESSION})',
        re.IGNORECASE,
    ),
    re.compile(
        rf'Meet\s+our\s+(?P<title>{TITLE_EXPRESSION})\s*,?\s*'
        rf'(?P<name>{NAME_EXPRESSION})',
        re.IGNORECASE,
    ),
)
PHONE_PATTERN = re.compile(r'\+?[\d][\d\s().-]{6,}\d')
BLOCK_TAGS = {'address', 'article', 'br', 'div', 'footer', 'h1', 'h2', 'h3', 'h4', 'li', 'p', 'section'}


class EvidenceTextParser(HTMLParser):
    """Convert fetched HTML to conservative, line-scoped evidence blocks."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.hidden_depth += 1
            return
        if self.hidden_depth:
            return
        if tag in BLOCK_TAGS:
            self.parts.append('\n')
        if tag == 'a':
            href = (dict(attrs).get('href') or '').strip()
            lowered = href.casefold()
            if lowered.startswith('mailto:'):
                self.parts.append(f' EMAIL:{href[7:].split("?", 1)[0]} ')
            elif lowered.startswith('tel:'):
                self.parts.append(f' PHONE:{href[4:].split("?", 1)[0]} ')

    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.hidden_depth = max(0, self.hidden_depth - 1)
        elif not self.hidden_depth and tag in BLOCK_TAGS:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden_depth and data.strip():
            self.parts.append(f' {data.strip()} ')

    def lines(self):
        return [
            ' '.join(line.split())
            for line in ''.join(self.parts).splitlines()
            if line.strip()
        ]


def _canonical_title(value):
    normalized = ' '.join(re.sub(r'[^a-z]+', ' ', value.casefold()).split())
    for role_group, title, _pattern in TITLE_PATTERNS:
        if normalized == ' '.join(re.sub(r'[^a-z]+', ' ', title.casefold()).split()):
            return role_group, title
    return None, None


def _page_confidence(source_url):
    category = _page_category(urlparse(source_url).path, '')
    return 'HIGH' if category in HIGH_CONFIDENCE_PAGES else 'MEDIUM'


def _line_email(line, website_domain):
    values = re.findall(r'EMAIL:([^\s]+)', line, flags=re.IGNORECASE)
    values.extend(EMAIL_PATTERN.findall(re.sub(r'EMAIL:[^\s]+', '', line)))
    return next((
        email for value in values
        if (email := _business_email(value, website_domain, allow_domain_email=True))
    ), None)


def _person_email(line, website_domain):
    email = _line_email(line, website_domain)
    if not email:
        return None
    local_part = email.rsplit('@', 1)[0].casefold()
    return None if local_part in BUSINESS_EMAIL_PREFIXES else email


def _line_phone(line):
    labelled = re.search(r'PHONE:([^\s]+(?:\s[^A-Za-z\s][^\s]*)*)', line, re.IGNORECASE)
    if labelled:
        return labelled.group(1).strip()
    cleaned = re.sub(r'EMAIL:[^\s]+', '', line)
    match = PHONE_PATTERN.search(cleaned)
    return match.group(0).strip() if match else None


def _contact(name, title, role_group, source_url, email=None, phone=None):
    identity = re.sub(r'[^a-z0-9]+', '-', f'{name or "team"}-{title}'.casefold()).strip('-')
    return {
        'provider_person_id': f'official-website:{identity}',
        'name': name,
        'title': title,
        'role_group': role_group,
        'department': {
            'it_leadership': 'Information Technology',
            'it_management': 'Information Technology',
            'general_manager': 'General Management',
            'executive': 'Executive Leadership',
            'operations': 'Operations',
            'sales': 'Sales',
        }[role_group],
        'organization_name': None,
        'company': None,
        'business_email': email,
        'email': email,
        'phone': phone,
        'linkedin_url': None,
        'source': SOURCE,
        'sources': [SOURCE],
        'business_email_source': source_url if email else None,
        'phone_source': source_url if phone else None,
        'source_url': source_url,
        'confidence': _page_confidence(source_url),
        'verification_status': None,
    }


def extract_official_website_contacts(html, source_url, website_domain):
    normalized_path = re.sub(
        r'[^a-z0-9]+', ' ', urlparse(source_url).path.casefold()
    ).strip()
    if 'sales' in normalized_path.split() and any(
        marker in normalized_path for marker in SALES_NEGATIVE_MARKERS
    ):
        return []
    parser = EvidenceTextParser()
    parser.feed(html)
    contacts = []
    for line in parser.lines():
        for pattern in PERSON_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            role_group, title = _canonical_title(match.group('title'))
            if not role_group:
                continue
            name = ' '.join(part.capitalize() for part in match.group('name').split())
            contacts.append(_contact(
                name, title, role_group, source_url,
                email=_person_email(line, website_domain), phone=_line_phone(line),
            ))
            break

        email = _line_email(line, website_domain)
        local_part = email.split('@', 1)[0].casefold() if email else ''
        if email and re.search(r'(^|[._-])sales($|[._-])', local_part):
            contacts.append(_contact(
                None, 'Sales Team', 'sales', source_url, email=email,
                phone=_line_phone(line),
            ))
    return contacts


def _deduplicate_contacts(contacts):
    deduplicated = []
    for contact in contacts:
        name = (contact.get('name') or '').casefold()
        key = (name, contact.get('role_group')) if name else (
            '', contact.get('role_group'), (contact.get('business_email') or '').casefold()
        )
        existing = next((item for item in deduplicated if item['_key'] == key), None)
        if existing:
            for field in ('business_email', 'email', 'phone'):
                if not existing.get(field) and contact.get(field):
                    existing[field] = contact[field]
            if existing.get('confidence') != 'HIGH' and contact.get('confidence') == 'HIGH':
                existing['confidence'] = 'HIGH'
                existing['source_url'] = contact['source_url']
            continue
        deduplicated.append({**contact, '_key': key})
    rank = {
        'it_leadership': 0, 'it_management': 1, 'general_manager': 2,
        'executive': 3, 'operations': 4, 'sales': 5,
    }
    deduplicated.sort(key=lambda item: (rank[item['role_group']], item['title'], item['name'] or ''))
    for contact in deduplicated:
        contact.pop('_key', None)
    return deduplicated[:MAX_CONTACTS]


class OfficialWebsitePeopleEnrichmentProvider(PeopleEnrichmentProvider):
    def search_decision_makers(self, business, category='hotels_resorts'):
        discovery = discover_official_website(
            hotel_name=business.get('name'), address=business.get('address'),
            brand=business.get('brand'), latitude=business.get('latitude'),
            longitude=business.get('longitude'), website=business.get('website'),
            contact_website=business.get('contact_website'),
            brand_website=business.get('brand_website'),
            domain_hint=business.get('domain_hint'), wikidata=business.get('wikidata'),
            wikipedia=business.get('wikipedia'), source=business.get('source'),
        )
        website = discovery.get('website')
        if not website:
            return self._result(business, category, [], 'NOT_FOUND')
        try:
            home_url, home_html = _fetch_html(website)
        except EnrichmentError as exc:
            raise PeopleEnrichmentError('The official business website could not be accessed.') from exc

        website_domain = (urlparse(home_url).hostname or '').removeprefix('www.')
        _, links = _extract_contacts(home_html, allowed_domain=website_domain)
        discovered, _default_urls = _discover_pages(home_url, links)
        selected_urls = []
        for page_type in PAGE_PRIORITY:
            page_url = discovered.get(page_type)
            if page_url and page_url != home_url and page_url not in selected_urls:
                selected_urls.append(page_url)
            if len(selected_urls) == MAX_PAGES - 1:
                break

        pages = [(home_url, home_html)]
        for page_url in selected_urls:
            try:
                pages.append(_fetch_html(page_url))
            except EnrichmentError:
                continue
        contacts = []
        for source_url, html in pages:
            page_contacts = extract_official_website_contacts(
                html, source_url, website_domain
            )
            for contact in page_contacts:
                contact['organization_name'] = business.get('name')
                contact['company'] = business.get('name')
            contacts.extend(page_contacts)
        contacts = _deduplicate_contacts(contacts)
        useful = any(contact.get('business_email') or contact.get('phone') for contact in contacts)
        status = 'FOUND' if useful else 'PARTIAL' if contacts else 'NOT_FOUND'
        return self._result(business, category, contacts, status)

    @staticmethod
    def _result(business, category, contacts, status):
        return {
            'business_name': business.get('name'),
            'hotel_name': business.get('name'),
            'category': category,
            'status': status,
            'contacts': contacts,
        }
