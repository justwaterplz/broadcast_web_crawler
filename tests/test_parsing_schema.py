from __future__ import annotations

from broadcast_web_crawler.parsing import parse_html
from broadcast_web_crawler.schema import discover_schema

HTML = b"""
<!doctype html>
<html>
  <head>
    <title>  Sample   Show </title>
    <meta name="description" content="A weekly show">
    <meta property="og:title" content="Sample Show">
    <script type="application/ld+json">
      {"name":"Sample Show","@type":"TVSeries","actor":[{"name":"Kim"}]}
    </script>
    <script>secretTrackingCode()</script>
  </head>
  <body>
    <main>
      <h1>Sample Show</h1>
      <ul><li>Episode 1</li><li>Episode 2</li></ul>
      <table>
        <caption>Episodes</caption>
        <tr><th>Number</th><th>Title</th></tr>
        <tr><td>1</td><td>Pilot</td></tr>
      </table>
    </main>
  </body>
</html>
"""


def test_html_parser_extracts_stable_structures() -> None:
    first = parse_html(HTML, source_url="https://EXAMPLE.com/show/1?utm_source=test")
    second = parse_html(HTML, source_url="https://example.com/show/1")

    assert first == second
    assert first.title == "Sample Show"
    assert first.source_url == "https://example.com/show/1"
    assert first.metadata_dict()["description"] == ("A weekly show",)
    assert first.json_ld[0] == {
        "@type": "TVSeries",
        "actor": [{"name": "Kim"}],
        "name": "Sample Show",
    }
    assert first.tables[0].columns == ("Number", "Title")
    assert first.tables[0].rows == (("1", "Pilot"),)
    assert first.lists == (("Episode 1", "Episode 2"),)
    assert "secretTrackingCode" not in first.text


def test_schema_discovery_reports_document_frequency() -> None:
    full = parse_html(HTML, source_url="https://example.com/show/1")
    sparse = parse_html("<main>Untitled body</main>", source_url="https://example.com/show/2")
    schema = discover_schema((full, sparse), min_frequency=0.5)
    profiles = {profile.path: profile for profile in schema.fields}

    assert schema.document_count == 2
    assert profiles["text"].frequency == 1
    assert profiles["title"].frequency == 0.5
    assert profiles["json_ld[].@type"].frequency == 0.5
    assert profiles["metadata.description[]"].observed_types == ("string",)
