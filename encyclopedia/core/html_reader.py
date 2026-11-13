"""Read entry records from encyclopedia HTML for core loading and CLI editing."""

from typing import Dict, List


def _extract_entries_from_encyclopedia_html(html_root) -> List[Dict]:
    """Extract entry dictionaries from encyclopedia format HTML.
    
    Args:
        html_root: Parsed HTML root element
        
    Returns:
        List of entry dictionaries
    """
    entries = []
    entry_divs = html_root.xpath(".//div[@role='ami_entry']")
    
    for entry_div in entry_divs:
        entry_dict = {}
        entry_dict['term'] = entry_div.get('term', '')
        entry_dict['canonical_term'] = entry_dict['term']
        entry_dict['wikidata_id'] = entry_div.get('wikidataID') or entry_div.get('wikidataid') or ''
        entry_dict['wikipedia_url'] = ''
        
        # Extract Wikipedia URL from links
        wiki_links = entry_div.xpath(".//a[contains(@href, 'wikipedia.org/wiki/')]")
        if wiki_links:
            entry_dict['wikipedia_url'] = wiki_links[0].get('href', '')
        
        # Extract diagnostic attributes (initialize to False if not present)
        wikipedia_page_retrieved = entry_div.get('data-wikipedia-page-retrieved')
        if wikipedia_page_retrieved:
            entry_dict['wikipedia_page_retrieved'] = wikipedia_page_retrieved.lower() == 'true'
        else:
            entry_dict['wikipedia_page_retrieved'] = False  # Default: not retrieved
        
        first_paragraph_retrieved = entry_div.get('data-first-paragraph-retrieved')
        if first_paragraph_retrieved:
            entry_dict['first_paragraph_retrieved'] = first_paragraph_retrieved.lower() == 'true'
        else:
            entry_dict['first_paragraph_retrieved'] = False  # Default: not retrieved
        
        # Extract description HTML - check multiple possible locations
        description_html = ''
        
        # Try p with class wpage_first_para (amilib standard)
        desc_elems = entry_div.xpath(".//p[@class='wpage_first_para']")
        if desc_elems:
            from amilib.xml_lib import XmlLib
            description_html = XmlLib.element_to_string(desc_elems[0])
        else:
            # Try any p element with actual text content (not empty)
            # Skip p with class mw-empty-elt (empty paragraphs)
            desc_ps = entry_div.xpath(".//p[text() and not(@class='mw-empty-elt')]")
            if desc_ps:
                from amilib.xml_lib import XmlLib
                # Get first non-empty paragraph
                for p_elem in desc_ps:
                    p_text = p_elem.text_content() if hasattr(p_elem, 'text_content') else (p_elem.text or '')
                    if p_text.strip():
                        description_html = XmlLib.element_to_string(p_elem)
                        break
            else:
                # Try getting text content from all p elements
                all_ps = entry_div.xpath(".//p")
                for p_elem in all_ps:
                    # Skip empty paragraphs
                    if p_elem.get('class') == 'mw-empty-elt':
                        continue
                    p_text = p_elem.text_content() if hasattr(p_elem, 'text_content') else (p_elem.text or '')
                    if p_text.strip():
                        from amilib.xml_lib import XmlLib
                        description_html = XmlLib.element_to_string(p_elem)
                        break
        
        entry_dict['description_html'] = description_html
        
        # Extract figure_html/image HTML - check for div[@title="figure"] wrapper (amilib standard)
        figure_html = ''
        figure_divs = entry_div.xpath(".//div[@title='figure']")
        if figure_divs:
            from amilib.xml_lib import XmlLib
            # Get the actual figure element (first child of the wrapper div)
            figure_children = figure_divs[0].xpath('./*')
            if figure_children:
                # Use the first child (the actual figure element: <a> or <figure>)
                figure_html = XmlLib.element_to_string(figure_children[0])
            else:
                # If no children, use the div itself
                figure_html = XmlLib.element_to_string(figure_divs[0])
        else:
            # Fallback: look for <figure> elements directly
            figure_elems = entry_div.xpath(".//figure")
            if figure_elems:
                from amilib.xml_lib import XmlLib
                figure_html = XmlLib.element_to_string(figure_elems[0])
            else:
                # Fallback: look for image links with wikipedia-image-link class
                img_links = entry_div.xpath(".//a[contains(@class, 'wikipedia-image-link')]")
                if img_links:
                    from amilib.xml_lib import XmlLib
                    figure_html = XmlLib.element_to_string(img_links[0])
        
        if figure_html:
            entry_dict['figure_html'] = figure_html
            # Also extract image_link URL if available
            if figure_divs:
                # Try to get href from <a> tag inside figure div
                a_elem = figure_divs[0].xpath(".//a[@href]")
                if a_elem:
                    href = a_elem[0].get('href', '')
                    if href:
                        if not href.startswith('http'):
                            if href.startswith('/wiki/File:') or href.startswith('/wiki/'):
                                href = f"https://en.wikipedia.org{href}"
                            elif href.startswith('/'):
                                href = f"https://en.wikipedia.org{href}"
                        entry_dict['image_link'] = href
                else:
                    # Try to get img src
                    img_elem = figure_divs[0].xpath(".//img[@src]")
                    if img_elem:
                        entry_dict['image_link'] = img_elem[0].get('src', '')
        
        entries.append(entry_dict)
    
    return entries

