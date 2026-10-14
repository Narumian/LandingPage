from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.references = []
        self.duplicates = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            if element_id in self.ids:
                self.duplicates.add(element_id)
            self.ids.add(element_id)

        if tag == "a" and attributes.get("href"):
            self.references.append(attributes["href"])
        if tag in {"img", "script", "source", "video", "audio"} and attributes.get("src"):
            self.references.append(attributes["src"])
        if tag == "link" and attributes.get("href"):
            self.references.append(attributes["href"])


def local_target(page, reference):
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc or reference.startswith("//"):
        return None, parsed.fragment

    decoded = unquote(parsed.path)
    target = (page.parent / decoded).resolve() if decoded else page.resolve()
    try:
        target.relative_to(ROOT)
    except ValueError:
        return None, parsed.fragment

    if target.is_dir() or decoded.endswith("/"):
        target = target / "index.html"
    return target, parsed.fragment


def main():
    pages = {}
    failures = []
    for page in sorted(ROOT.rglob("*.html")):
        if ".git" in page.parts:
            continue
        parser = PageParser()
        try:
            parser.feed(page.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as error:
            failures.append(f"{page.relative_to(ROOT)}: {error}")
            continue
        if parser.duplicates:
            failures.append(f"{page.relative_to(ROOT)}: duplicate id(s): {', '.join(sorted(parser.duplicates))}")
        pages[page.resolve()] = parser

    for page, parser in pages.items():
        for reference in parser.references:
            target, fragment = local_target(page, reference)
            if target is None:
                continue
            if not target.is_file():
                failures.append(f"{page.relative_to(ROOT)}: missing local target: {reference}")
                continue
            if fragment and target.suffix == ".html":
                target_parser = pages.get(target)
                if target_parser and fragment not in target_parser.ids:
                    failures.append(f"{page.relative_to(ROOT)}: missing anchor: {reference}")

    if failures:
        print("Site checks failed:")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print(f"Checked {len(pages)} HTML pages and their local links.")


if __name__ == "__main__":
    main()
