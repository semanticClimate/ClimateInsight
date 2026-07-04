import re


def extract_citations(answer: str) -> list[dict]:

    cited = re.findall(r"\[([^\]]+)\]", answer)

    return [
        {"section": section}
        for section in dict.fromkeys(cited)
    ]