from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Mapping

_VOID_HTML_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


@dataclass
class HtmlNode:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    order: int = 0
    children: list["HtmlNode"] = field(default_factory=list)
    _content: list[str | "HtmlNode"] = field(default_factory=list)

    def append_child(self, node: "HtmlNode") -> None:
        self.children.append(node)
        self._content.append(node)

    def append_text(self, text: str) -> None:
        self._content.append(text)

    def text(self) -> str:
        return "".join(
            item if isinstance(item, str) else item.text() for item in self._content
        )

    def normalized_text(self) -> str:
        return " ".join(self.text().split())

    def find_all(
        self,
        tag: str | None = None,
        attrs: Mapping[str, str | bool] | None = None,
    ) -> list["HtmlNode"]:
        matches: list[HtmlNode] = []
        for child in self.children:
            if child.matches(tag, attrs):
                matches.append(child)
            matches.extend(child.find_all(tag, attrs))
        return matches

    def require(
        self,
        tag: str | None = None,
        attrs: Mapping[str, str | bool] | None = None,
    ) -> "HtmlNode":
        matches = self.find_all(tag, attrs)
        if not matches:
            description = tag or "node"
            if attrs:
                description += f" with attrs {dict(attrs)!r}"
            raise AssertionError(f"missing HTML {description}")
        return matches[0]

    def count(
        self,
        tag: str | None = None,
        attrs: Mapping[str, str | bool] | None = None,
    ) -> int:
        return len(self.find_all(tag, attrs))

    def by_testid(self, testid: str) -> "HtmlNode":
        return self.require(attrs={"data-testid": testid})

    def matches(
        self,
        tag: str | None = None,
        attrs: Mapping[str, str | bool] | None = None,
    ) -> bool:
        if tag is not None and self.tag != tag:
            return False
        for name, expected in (attrs or {}).items():
            if expected is True:
                if name not in self.attrs:
                    return False
            elif self.attrs.get(name) != expected:
                return False
        return True


class _HtmlTreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HtmlNode("document")
        self._stack = [self.root]
        self._order = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._order += 1
        node = HtmlNode(
            tag,
            attrs={name: value or "" for name, value in attrs},
            order=self._order,
        )
        self._stack[-1].append_child(node)
        if tag not in _VOID_HTML_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                break

    def handle_data(self, data: str) -> None:
        self._stack[-1].append_text(data)


def parse_html(markup: str) -> HtmlNode:
    parser = _HtmlTreeParser()
    parser.feed(markup)
    parser.close()
    return parser.root
