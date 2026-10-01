"""
concept_map.py
--------------
Generates dynamic Mermaid.js flowcharts / concept mind maps from
RAG answers to visualize key climate mechanisms, causes, and consequences.
"""

import re


def generate_concept_map(question: str, answer: str) -> str | None:
    """
    Analyzes the user question and LLM answer to construct a valid
    Mermaid.js flowchart (graph TD) representing key concepts and relationships.

    Returns a Mermaid diagram string if relevant relationships are found,
    otherwise returns None.
    """
    if not answer or len(answer.strip()) < 40:
        return None

    nodes = []
    edges = []
    seen_nodes = set()

    def clean_label(text: str) -> str:
        text = re.sub(r"\[S\d+\]", "", text)
        text = re.sub(r"[^\w\s\-\.\%\°\(\)]", "", text)
        text = text.strip()
        if len(text) > 45:
            text = text[:42] + "..."
        return text

    def add_node(label: str) -> str:
        cleaned = clean_label(label)
        if not cleaned:
            return ""
        node_id = re.sub(r"[^\w]", "_", cleaned.lower()).strip("_")
        if not node_id:
            node_id = f"node_{len(seen_nodes)}"
        if node_id not in seen_nodes:
            seen_nodes.add(node_id)
            nodes.append(f'  {node_id}["{cleaned}"]')
        return node_id

    # Common climate cause-and-effect relationship patterns
    patterns = [
        (r"([\w\s]{3,35})\s+(?:leads to|causes|results in|drives|triggers)\s+([\w\s]{3,35})", "-->"),
        (r"([\w\s]{3,35})\s+(?:increases|amplifies|boosts|elevates)\s+([\w\s]{3,35})", "-- Increases -->"),
        (r"([\w\s]{3,35})\s+(?:reduces|decreases|lowers|mitigates)\s+([\w\s]{3,35})", "-- Reduces -->"),
        (r"([\w\s]{3,35})\s+(?:due to|caused by|driven by|resulting from)\s+([\w\s]{3,35})", "<-- Caused by --"),
    ]

    sentences = re.split(r"(?<=[.!?])\s+|\n+", answer)
    for sentence in sentences:
        for pattern, connector in patterns:
            matches = re.findall(pattern, sentence, re.IGNORECASE)
            for cause, effect in matches:
                cause_id = add_node(cause)
                effect_id = add_node(effect)
                if cause_id and effect_id and cause_id != effect_id:
                    edges.append(f"  {cause_id} {connector} {effect_id}")

    # Key climate fallback concept graph if no regex matches are found
    if len(edges) < 1:
        text = (question + " " + answer).lower()
        if "heatwave" in text or "ocean" in text or "marine" in text:
            n1 = add_node("GHG Emissions / Global Warming")
            n2 = add_node("Increased Ocean Heat Absorption")
            n3 = add_node("Marine Heatwaves (MHWs)")
            n4 = add_node("Thermal Stress & Coral Bleaching")
            edges = [f"  {n1} --> {n2}", f"  {n2} --> {n3}", f"  {n3} --> {n4}"]
        elif "warming" in text or "temperature" in text or "carbon" in text:
            n1 = add_node("Greenhouse Gas Concentration")
            n2 = add_node("Radiative Forcing")
            n3 = add_node("Global Mean Surface Temp Rise")
            n4 = add_node("Extreme Weather & Sea Level Rise")
            edges = [f"  {n1} --> {n2}", f"  {n2} --> {n3}", f"  {n3} --> {n4}"]
        elif "sea level" in text or "coastal" in text:
            n1 = add_node("Global Warming")
            n2 = add_node("Glacier Melt & Thermal Expansion")
            n3 = add_node("Sea Level Rise")
            n4 = add_node("Coastal Inundation & Erosion")
            edges = [f"  {n1} --> {n2}", f"  {n2} --> {n3}", f"  {n3} --> {n4}"]

    if not nodes or not edges:
        return None

    # Deduplicate edges
    unique_edges = list(dict.fromkeys(edges))

    lines = ["graph TD"] + nodes + unique_edges
    return "\n".join(lines)
