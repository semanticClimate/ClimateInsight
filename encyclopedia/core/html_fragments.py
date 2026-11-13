"""HTML fragments for paper evidence, display controls, and missing articles."""

from pathlib import Path
from urllib.parse import quote

import lxml.etree as ET

def _highlight_sentence(parent, example: dict) -> None:
    """Write a sentence with the matched term marked."""
    sentence = str(example.get("sentence") or "")
    start = int(example.get("start") or 0)
    end = int(example.get("end") or 0)
    matched = str(example.get("matched") or "")
    hit = ""
    before = sentence
    after = ""
    if 0 <= start < end <= len(sentence):
        before, hit, after = sentence[:start], sentence[start:end], sentence[end:]
    elif matched and matched in sentence:
        start = sentence.find(matched)
        before, hit, after = sentence[:start], matched, sentence[start + len(matched):]
    parent.text = before
    if hit:
        mark = ET.SubElement(parent, "span")
        mark.set("class", "paper-hit")
        mark.text = hit
        mark.tail = after


def _append_paper_examples(parent, examples) -> None:
    """Links back to the papers, one sentence from each."""
    if not examples:
        return
    listing = ET.SubElement(parent, "ul")
    listing.set("class", "paper-examples")
    for index, example in enumerate(examples, start=1):
        item = ET.SubElement(listing, "li")
        item.set("class", "paper-example")
        item.set("data-example", str(index))
        source = str(example.get("source") or "")
        label = Path(source).stem or source
        url = str(example.get("url") or "")
        if url:
            link = ET.SubElement(item, "a")
            link.set("href", url)
        else:
            link = ET.SubElement(item, "span")
        link.set("class", "paper-link")
        link.text = label
        sentence = ET.SubElement(item, "span")
        sentence.set("class", "paper-sentence")
        _highlight_sentence(sentence, example)


def _append_example_limit_control(parent, limit: int) -> None:
    """Number of paper examples to show, with Reset restoring the maximum."""
    if limit <= 0:
        return
    parent.set("data-example-limit", str(limit))
    box = ET.SubElement(parent, "div")
    box.set("class", "example-limit")
    label = ET.SubElement(box, "label")
    label.set("for", "example-limit")
    label.text = "Paper examples "
    field = ET.SubElement(label, "input")
    field.set("type", "number")
    field.set("id", "example-limit")
    field.set("min", "0")
    field.set("max", str(limit))
    field.set("value", str(limit))
    button = ET.SubElement(box, "button")
    button.set("type", "button")
    button.set("id", "example-limit-reset")
    button.text = "Reset"


def _append_example_limit_script(parent) -> None:
    script = ET.SubElement(parent, "script")
    script.text = (
        "(function () {"
        "var root = document.querySelector('[role=ami_encyclopedia]');"
        "if (!root) return;"
        "var max = Number(root.getAttribute('data-example-limit') || '3');"
        "var input = document.getElementById('example-limit');"
        "var reset = document.getElementById('example-limit-reset');"
        "function apply(count) {"
        "var items = root.querySelectorAll('.paper-example');"
        "for (var i = 0; i < items.length; i++) {"
        "var n = Number(items[i].getAttribute('data-example') || '0');"
        "if (n > count) items[i].setAttribute('hidden', 'hidden');"
        "else items[i].removeAttribute('hidden');"
        "}"
        "}"
        "if (input) input.addEventListener('input', function () { apply(Number(input.value || '0')); });"
        "if (reset) reset.addEventListener('click', function () {"
        "if (input) input.value = String(max); apply(max);"
        "});"
        "apply(max);"
        "})();"
    )


def _append_missing_article_page(parent, items) -> None:
    """One encyclopedia page listing every term that has no Wikipedia article."""
    entry = ET.SubElement(parent, "div")
    entry.set("role", "ami_entry")
    entry.set("class", "encyclopedia-entry missing-articles")
    entry.set("term", "No Wikipedia article")
    entry.set("title", "No Wikipedia article")
    heading = ET.SubElement(entry, "h2")
    heading.text = "No Wikipedia article"
    note = ET.SubElement(entry, "p")
    note.set("class", "no-description")
    note.text = "No description: no Wikipedia article"
    listing = ET.SubElement(entry, "ul")
    listing.set("class", "missing-article-list")
    for name, examples in items:
        item = ET.SubElement(listing, "li")
        link = ET.SubElement(item, "a")
        link.set("href", "https://en.wikipedia.org/w/index.php?search=" + quote(name))
        link.text = name
        _append_paper_examples(item, examples)
