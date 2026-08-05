import json

from app.application.evidence_search_service import EvidenceSearchService


class FakeResponse:
    def __init__(self, body: str) -> None:
        self.body = body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def read(self):
        return self.body


def test_search_many_fetches_pubmed_cards_and_deduplicates(monkeypatch) -> None:
    urls: list[str] = []

    def fake_urlopen(url: str, timeout: int):
        urls.append(url)
        if "esearch.fcgi" in url:
            return FakeResponse(json.dumps({"esearchresult": {"idlist": ["27433992", "27433992"]}}))
        return FakeResponse(
            """
            <PubmedArticleSet>
              <PubmedArticle>
                <MedlineCitation>
                  <PMID>27433992</PMID>
                  <Article>
                    <Journal>
                      <JournalIssue><PubDate><Year>2017</Year></PubDate></JournalIssue>
                      <Title>Journal of Sports Sciences</Title>
                    </Journal>
                    <ArticleTitle>Resistance training volume enhances muscle hypertrophy</ArticleTitle>
                    <Abstract><AbstractText>Systematic review and meta-analysis on resistance training volume.</AbstractText></Abstract>
                    <AuthorList><Author><LastName>Schoenfeld</LastName><Initials>BJ</Initials></Author></AuthorList>
                  </Article>
                </MedlineCitation>
                <PubmedData><ArticleIdList><ArticleId IdType="doi">10.1080/example</ArticleId></ArticleIdList></PubmedData>
              </PubmedArticle>
            </PubmedArticleSet>
            """
        )

    monkeypatch.setattr("app.application.evidence_search_service.urlopen", fake_urlopen)

    result = EvidenceSearchService().search_many([
        "resistance training hypertrophy volume systematic review meta analysis",
        "resistance training hypertrophy volume systematic review meta analysis",
    ])

    assert result["search_queries"] == ["resistance training hypertrophy volume systematic review meta analysis"]
    assert len(result["used_references"]) == 1
    assert result["used_references"][0]["pmid"] == "27433992"
    assert result["used_references"][0]["doi"] == "10.1080/example"
    assert result["used_references"][0]["evidence_level"] == "solid"
    assert len([url for url in urls if "esearch.fcgi" in url]) == 1


def test_search_many_filters_sensitive_queries(monkeypatch) -> None:
    calls: list[str] = []

    def fake_urlopen(url: str, timeout: int):
        calls.append(url)
        return FakeResponse(json.dumps({"esearchresult": {"idlist": []}}))

    monkeypatch.setattr("app.application.evidence_search_service.urlopen", fake_urlopen)

    result = EvidenceSearchService().search_many(["email user@example.com resistance training", "token secret"])

    assert result["search_queries"] == []
    assert result["used_references"] == []
    assert calls == []
    assert "No se ejecutaron busquedas" in " ".join(result["limitations"])
