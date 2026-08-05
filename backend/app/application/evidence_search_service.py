from dataclasses import dataclass
import json
from typing import Any
import xml.etree.ElementTree as ET
from urllib.parse import urlencode
from urllib.request import urlopen

NCBI_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_RETMAX = 5
DEFAULT_TIMEOUT_SECONDS = 12


class EvidenceSearchError(Exception):
    pass


@dataclass(frozen=True)
class EvidenceCard:
    title: str
    authors: list[str]
    year: str | None
    journal: str | None
    pmid: str
    doi: str | None
    abstract: str | None
    query: str
    evidence_level: str
    source: str = "pubmed"

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "journal": self.journal,
            "pmid": self.pmid,
            "doi": self.doi,
            "abstract": self.abstract,
            "query": self.query,
            "evidence_level": self.evidence_level,
        }


class EvidenceSearchService:
    def search_many(self, queries: list[str], *, retmax: int = DEFAULT_RETMAX) -> dict[str, Any]:
        clean_queries = self._clean_queries(queries)
        cards: list[EvidenceCard] = []
        errors: list[str] = []
        seen_pmids: set[str] = set()
        for query in clean_queries:
            try:
                for card in self.search_pubmed(query, retmax=retmax):
                    if card.pmid not in seen_pmids:
                        seen_pmids.add(card.pmid)
                        cards.append(card)
            except EvidenceSearchError as error:
                errors.append(f"{query}: {error}")
        return {
            "search_queries": clean_queries,
            "used_references": [card.as_dict() for card in cards[:12]],
            "limitations": self._limitations(clean_queries, cards, errors),
            "errors": errors,
        }

    def search_pubmed(self, query: str, *, retmax: int = DEFAULT_RETMAX) -> list[EvidenceCard]:
        clean_query = self._clean_query(query)
        if not clean_query:
            return []
        pmids = self._search_pmids(clean_query, retmax=retmax)
        if not pmids:
            return []
        return self._fetch_cards(clean_query, pmids)

    def _search_pmids(self, query: str, *, retmax: int) -> list[str]:
        params = urlencode(
            {
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": max(1, min(retmax, 10)),
                "sort": "relevance",
                "tool": "zenith-coach",
            }
        )
        raw = self._get(f"{NCBI_BASE_URL}/esearch.fcgi?{params}")
        try:
            parsed = json.loads(raw)
            ids = parsed.get("esearchresult", {}).get("idlist", [])
        except (TypeError, ValueError) as error:
            raise EvidenceSearchError("PubMed search returned invalid JSON.") from error
        return [str(item) for item in ids if str(item).strip()]

    def _fetch_cards(self, query: str, pmids: list[str]) -> list[EvidenceCard]:
        params = urlencode({"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", "tool": "zenith-coach"})
        raw = self._get(f"{NCBI_BASE_URL}/efetch.fcgi?{params}")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as error:
            raise EvidenceSearchError("PubMed fetch returned invalid XML.") from error

        cards: list[EvidenceCard] = []
        for article in root.findall(".//PubmedArticle"):
            pmid = self._text(article.find(".//PMID"))
            title = self._all_text(article.find(".//ArticleTitle"))
            if not pmid or not title:
                continue
            abstract = "\n".join(
                part
                for part in [self._all_text(item) for item in article.findall(".//Abstract/AbstractText")]
                if part
            ) or None
            cards.append(
                EvidenceCard(
                    title=title[:500],
                    authors=self._authors(article),
                    year=self._year(article),
                    journal=self._all_text(article.find(".//Journal/Title")) or self._all_text(article.find(".//MedlineTA")),
                    pmid=pmid,
                    doi=self._doi(article),
                    abstract=abstract[:1_500] if abstract else None,
                    query=query,
                    evidence_level=self._evidence_level(title, abstract),
                )
            )
        return cards

    def _get(self, url: str) -> str:
        try:
            with urlopen(url, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
                return response.read().decode("utf-8")
        except OSError as error:
            raise EvidenceSearchError("PubMed request failed.") from error

    def _clean_queries(self, queries: list[str]) -> list[str]:
        cleaned: list[str] = []
        for query in queries[:8]:
            clean = self._clean_query(query)
            if clean and clean not in cleaned:
                cleaned.append(clean)
        return cleaned

    def _clean_query(self, query: str) -> str:
        if not isinstance(query, str):
            return ""
        clean = " ".join(query.strip().split())[:180]
        blocked_fragments = ["@", "password", "token", "email", "username"]
        if any(fragment in clean.lower() for fragment in blocked_fragments):
            return ""
        return clean

    def _limitations(self, queries: list[str], cards: list[EvidenceCard], errors: list[str]) -> list[str]:
        limitations = [
            "PubMed no cubre toda la literatura aplicada de entrenamiento y no siempre ofrece texto completo.",
            "Las referencias recuperadas deben interpretarse por aplicabilidad al usuario, no como reglas universales.",
        ]
        if not cards:
            limitations.append("No se recuperaron referencias suficientes; el plan debe declarar la incertidumbre.")
        if errors:
            limitations.append("Algunas busquedas fallaron por disponibilidad de PubMed o formato de respuesta.")
        if not queries:
            limitations.append("No se ejecutaron busquedas porque no hubo consultas cientificas validas.")
        return limitations

    def _authors(self, article: ET.Element) -> list[str]:
        authors: list[str] = []
        for author in article.findall(".//AuthorList/Author")[:8]:
            last_name = self._text(author.find("LastName"))
            initials = self._text(author.find("Initials"))
            collective = self._text(author.find("CollectiveName"))
            if collective:
                authors.append(collective)
            elif last_name:
                authors.append(f"{last_name} {initials}".strip())
        return authors

    def _year(self, article: ET.Element) -> str | None:
        for path in [".//JournalIssue/PubDate/Year", ".//ArticleDate/Year", ".//PubMedPubDate/Year"]:
            year = self._text(article.find(path))
            if year:
                return year
        return None

    def _doi(self, article: ET.Element) -> str | None:
        for article_id in article.findall(".//ArticleId"):
            if article_id.attrib.get("IdType") == "doi":
                return self._text(article_id)
        return None

    def _evidence_level(self, title: str, abstract: str | None) -> str:
        text = f"{title} {abstract or ''}".lower()
        if any(marker in text for marker in ["systematic review", "meta-analysis", "meta analysis", "position stand", "guideline"]):
            return "solid"
        if any(marker in text for marker in ["randomized", "controlled trial", "clinical trial"]):
            return "moderate"
        return "practical"

    def _text(self, element: ET.Element | None) -> str | None:
        if element is None or element.text is None:
            return None
        text = " ".join(element.text.strip().split())
        return text or None

    def _all_text(self, element: ET.Element | None) -> str | None:
        if element is None:
            return None
        text = " ".join("".join(element.itertext()).strip().split())
        return text or None


evidence_search_service = EvidenceSearchService()
