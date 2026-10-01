from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "public-site"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            values = dict(attrs)
            if values.get("href"):
                self.links.append(values["href"] or "")


def test_public_site_has_production_identity_and_required_policy_pages() -> None:
    assert (SITE / "CNAME").read_text(encoding="utf-8").strip() == (
        "de-mail.liminalmemory.com"
    )
    homepage = (SITE / "index.html").read_text(encoding="utf-8")
    assert "de-Mail Desktop by Liminal" in homepage
    assert "alex@liminalmemory.com" in homepage
    assert "OAuth approval and Windows code signing" in homepage
    for page in ("privacy.html", "terms.html", "security.html", "delete-data.html"):
        assert (SITE / page).is_file()


def test_every_internal_site_link_resolves_to_a_file() -> None:
    for page in SITE.glob("*.html"):
        parser = LinkParser()
        parser.feed(page.read_text(encoding="utf-8"))
        for link in parser.links:
            if ":" not in link and not link.startswith("#"):
                assert (SITE / link).is_file(), f"Broken link in {page.name}: {link}"


def test_privacy_claims_match_the_local_only_security_boundary() -> None:
    combined = "\n".join(
        (SITE / name).read_text(encoding="utf-8")
        for name in ("index.html", "privacy.html", "security.html", "delete-data.html")
    )
    assert "gmail.readonly" in combined
    assert "does not operate a server" in combined
    assert "does not download or execute an update" in combined
    assert "Google Account connections" in combined
    assert "automatically" in combined
