"""Wikipedia descriptions and images shared by builders and editing commands."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from encyclopedia.core.encyclopedia import AmiEncyclopedia


def _clean_wikipedia_paragraph(para_elem):
    """Copy a paragraph and remove non-prose elements, preserving their tails."""
    # Wikipedia includes template styles inside paragraphs. Work on a copy so
    # filtering boilerplate does not alter the cached page used for other features.
    para_elem = copy.deepcopy(para_elem)
    for node in para_elem.xpath('.//style | .//script | .//link | .//meta | .//table | .//figure'):
        parent = node.getparent()
        if parent is None:
            continue
        previous = node.getprevious()
        if node.tail:
            if previous is None:
                parent.text = (parent.text or '') + node.tail
            else:
                previous.tail = (previous.tail or '') + node.tail
        parent.remove(node)
    
    return para_elem


def _has_non_empty_description(entry_dict: Dict) -> bool:
    """Check if entry has a non-empty description.
    
    Args:
        entry_dict: Entry dictionary
        
    Returns:
        True if entry has non-empty description HTML
    """
    description_html = str(entry_dict.get('description_html') or '').strip()
    if not description_html:
        return False
    
    # Check if it's just empty tags
    from lxml.html import fromstring
    try:
        desc_root = _clean_wikipedia_paragraph(fromstring(description_html.encode('utf-8')))
        text_content = desc_root.text_content() if hasattr(desc_root, 'text_content') else ''
        return bool(text_content.strip())
    except Exception:
        # If parsing fails, assume it has content
        return True


def _get_wikipedia_page_for_entry(entry_dict: Dict):
    """Get WikipediaPage object for entry.
    
    Args:
        entry_dict: Entry dictionary
        
    Returns:
        WikipediaPage object or None
    """
    from amilib.wikimedia import WikipediaPage
    
    # Try using existing URL first (more efficient)
    wikipedia_url = entry_dict.get('wikipedia_url', '').strip()
    if wikipedia_url:
        try:
            return WikipediaPage.lookup_wikipedia_page_for_url(wikipedia_url)
        except Exception:
            pass
    
    # Fallback to term lookup
    term = entry_dict.get('term', entry_dict.get('canonical_term', ''))
    if term:
        try:
            return WikipediaPage.lookup_wikipedia_page_for_term(term)
        except Exception:
            pass
    
    return None


def _extract_wikidata_id_from_wikipedia_page(wikipedia_page) -> Optional[str]:
    """Extract Wikidata ID from WikipediaPage object.
    
    Args:
        wikipedia_page: WikipediaPage object
        
    Returns:
        Wikidata ID (Q/P format) or None
    """
    try:
        wikidata_url = wikipedia_page.get_wikidata_item()
        if wikidata_url and '/wiki/' in wikidata_url:
            return wikidata_url.split('/wiki/')[-1]
    except Exception:
        pass
    return None


def _filter_wikipedia_messages(text: str) -> bool:
    """Check if text contains Wikipedia error/redirect messages that should be filtered.
    
    Args:
        text: Text to check
        
    Returns:
        True if text should be filtered out (contains error messages)
    """
    if not text:
        return True  # Filter empty text
    
    text_stripped = text.strip()
    if not text_stripped or len(text_stripped) < 10:
        return True  # Filter very short text (likely empty or just whitespace)
    
    text_lower = text_stripped.lower()
    
    # Strong filter patterns (always filter)
    strong_patterns = [
        "other reasons this message may be displayed",
        "this is an accepted version of this page",
        "this is the latest accepted revision",
        "page version status",
    ]
    
    for pattern in strong_patterns:
        if pattern in text_lower:
            return True
    
    # Weak filter patterns (only filter if text is short - likely disambiguation)
    # Longer paragraphs with these patterns might be legitimate content
    weak_patterns = [
        "this page was last edited",
        "you may be looking for",
        "redirected from",
    ]
    
    # Only filter weak patterns if text is short (likely disambiguation message)
    if len(text_stripped) < 150:
        for pattern in weak_patterns:
            if pattern in text_lower:
                return True
        
        # Filter "this article is about" only if it's a short disambiguation message
        if "this article is about" in text_lower and len(text_stripped) < 200:
            # Check if it's clearly a disambiguation (contains "for" and "see")
            if " for " in text_lower and " see " in text_lower:
                return True
    
    return False


def _extract_definition_from_paragraph(para_elem) -> tuple:
    """Extract definition (first sentence) separately from description.
    
    Preserves HTML structure and wraps first sentence in span with class "first_sentence_definition".
    Uses paragraph element from amilib (already filtered and processed).
    
    Args:
        para_elem: Paragraph element from Wikipedia (from amilib's create_first_wikipedia_para)
        
    Returns:
        Tuple of (definition_html, description_html) where:
        - definition_html: First sentence wrapped in <span class="first_sentence_definition">
        - description_html: Full paragraph HTML (preserved with all HTML structure)
    """
    from amilib.xml_lib import XmlLib
    import lxml.etree as ET
    import re

    para_elem = _clean_wikipedia_paragraph(para_elem)

    # Get text content
    para_text = para_elem.text_content() if hasattr(para_elem, 'text_content') else ''
    
    # Filter out obvious Wikipedia error messages (safety check)
    # amilib already filters by length, but check for error message patterns
    if _filter_wikipedia_messages(para_text):
        return None, None
    
    # Extract first sentence (ends with period followed by space or end)
    first_sentence_match = re.match(r'^([^.]*\.)(?:\s|$)', para_text)
    
    if first_sentence_match:
        first_sentence_text = first_sentence_match.group(1).strip()
        
        # Create definition span with first sentence
        definition_span = ET.Element("span")
        definition_span.attrib["class"] = "first_sentence_definition"
        definition_span.text = first_sentence_text
        
        # Ensure paragraph has wpage_first_para class (amilib should set this, but ensure it)
        if not para_elem.get('class') or 'wpage_first_para' not in para_elem.get('class', ''):
            para_elem.set('class', 'wpage_first_para')
        
        description_html = XmlLib.element_to_string(para_elem)
        definition_html = XmlLib.element_to_string(definition_span)
        return definition_html, description_html
    
    # If no clear first sentence, return full paragraph as description
    # Ensure paragraph has wpage_first_para class
    if not para_elem.get('class') or 'wpage_first_para' not in para_elem.get('class', ''):
        para_elem.set('class', 'wpage_first_para')
    
    description_html = XmlLib.element_to_string(para_elem)
    return None, description_html


def _get_first_paragraph_html_from_wikipedia_page(wikipedia_page) -> tuple:
    """Get first paragraph HTML from WikipediaPage using amilib methods.
    
    Uses amilib's create_first_wikipedia_para() method which handles filtering
    and extraction. If that fails, falls back to manual extraction using
    amilib's get_main_element() method.
    
    Args:
        wikipedia_page: WikipediaPage object
        
    Returns:
        Tuple of (definition_html, description_html) where:
        - definition_html: First sentence as span (or None)
        - description_html: Full paragraph HTML (or None)
    """
    # Primary method: Use amilib's create_first_wikipedia_para() - it handles filtering and extraction
    # This method uses get_main_element() which cleans the page and filters paragraphs
    para_obj = None
    try:
        para_obj = wikipedia_page.create_first_wikipedia_para()
    except Exception:
        # If amilib method raises exception, fall back to manual extraction
        pass
    
    if para_obj is not None and para_obj.para_element is not None:
        # Use the paragraph element from amilib (already filtered and processed)
        para_elem = para_obj.para_element
        
        # Extract definition and description from the paragraph
        # The paragraph already has class 'wpage_first_para' set by amilib
        result = _extract_definition_from_paragraph(para_elem)
        # Only return if extraction succeeded (not filtered out)
        if result[0] is not None or result[1] is not None:
            return result
        # If extraction filtered it out, continue to fallback
    
    # Fallback: If create_first_wikipedia_para() fails or returns None para_element,
    # use get_main_element() and extract manually
    # This handles edge cases where amilib's method doesn't find a paragraph
    main_elem = None
    try:
        main_elem = wikipedia_page.get_main_element()
    except Exception:
        pass

    roots = [main_elem, getattr(wikipedia_page, 'html_elem', None)]
    for root in roots:
        if root is None:
            continue
        paragraphs = root.xpath('.//p[not(ancestor::table or ancestor::aside or ancestor::nav)]')
        for para_elem in paragraphs[:20]:
            result = _extract_definition_from_paragraph(para_elem)
            if result[1] is not None:
                return result
    
    # No valid paragraph found
    return None, None


def add_wikipedia_feature(entry_dict: Dict, encyclopedia: AmiEncyclopedia):
    """Add Wikipedia description to entry using amilib methods.
    
    Uses WikipediaPage.create_first_wikipedia_para() or similar amilib methods
    to extract the first paragraph with proper wpage_first_para class.
    
    Args:
        entry_dict: Entry dictionary
        encyclopedia: Encyclopedia instance (for lookups)
    """
    term = entry_dict.get('term', entry_dict.get('canonical_term', ''))
    if not term:
        return
    
    # Check if already has Wikipedia description - only skip if BOTH description AND URL exist
    # If URL exists but description is missing/empty, we should still try to add it
    has_description = _has_non_empty_description(entry_dict)
    has_url = entry_dict.get('wikipedia_url')
    
    if has_description and has_url:
        print(f"  Entry '{term}' already has Wikipedia description")
        return
    
    # If we have URL but no description, try to re-fetch (might be a redirect/disambiguation issue)
    if has_url and not has_description:
        print(f"  Entry '{term}' has Wikipedia URL but no description, re-fetching...")
    
    # Get Wikipedia page - always try to fetch, even if URL exists
    print(f"  Looking up Wikipedia for '{term}'...")
    wikipedia_page = _get_wikipedia_page_for_entry(entry_dict)
    
    # Track diagnostic information
    entry_dict['wikipedia_page_retrieved'] = False
    entry_dict['first_paragraph_retrieved'] = False
    
    if not wikipedia_page:
        print(f"  ⚠ No Wikipedia page found for '{term}'")
        # If we had a URL but lookup failed, clear it
        if has_url:
            print(f"    Warning: Previous URL {entry_dict.get('wikipedia_url')} is no longer valid")
        return
    
    # Wikipedia page was retrieved
    entry_dict['wikipedia_page_retrieved'] = True
    page_url = wikipedia_page.url if hasattr(wikipedia_page, 'url') else 'N/A'
    original_url = entry_dict.get('wikipedia_url', '')
    
    print(f"  ✓ Wikipedia page retrieved: {page_url}")
    if original_url and original_url != page_url:
        print(f"    DEBUG: URL changed from {original_url} to {page_url} (possible redirect)")
    
    # Check for redirect indicators in the page
    if hasattr(wikipedia_page, 'html_elem') and wikipedia_page.html_elem is not None:
        redirect_indicators = wikipedia_page.html_elem.xpath(".//div[@class='redirectMsg'] | .//span[@class='mw-redirect']")
        if redirect_indicators:
            print(f"    DEBUG: Found redirect indicators in page HTML")
    
    # Save downloaded page HTML for debugging
    try:
        from encyclopedia.utils.resources import Resources
        from pathlib import Path
        debug_dir = Resources.get_temp_dir("debug", "wikipedia_pages")
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        # Create safe filename from term
        safe_term = term.replace(' ', '_').replace('/', '_')[:50]
        debug_file = Path(debug_dir, f"{safe_term}.html")
        
        # Save HTML if html_elem exists
        if hasattr(wikipedia_page, 'html_elem') and wikipedia_page.html_elem is not None:
            from amilib.xml_lib import XmlLib
            html_content = XmlLib.element_to_string(wikipedia_page.html_elem)
            debug_file.write_text(html_content, encoding='utf-8')
            print(f"    DEBUG: Saved downloaded page HTML to: {debug_file}")
        elif hasattr(wikipedia_page, 'html') and wikipedia_page.html:
            debug_file.write_text(wikipedia_page.html, encoding='utf-8')
            print(f"    DEBUG: Saved downloaded page HTML to: {debug_file}")
        else:
            print(f"    DEBUG: No HTML content available to save")
    except Exception as e:
        print(f"    DEBUG: Could not save page HTML: {e}")
    
    # Extract definition and description separately using amilib methods
    definition_html, description_html = _get_first_paragraph_html_from_wikipedia_page(wikipedia_page)
    
    if description_html or definition_html:
        # First paragraph was retrieved
        entry_dict['first_paragraph_retrieved'] = True
        print(f"  ✓ First paragraph retrieved")
        # Ensure description_html has the wpage_first_para class for proper identification
        if description_html and 'wpage_first_para' not in description_html:
            # Parse and add class if missing
            try:
                from lxml.etree import fromstring
                from amilib.xml_lib import XmlLib
                desc_root = fromstring(description_html.encode('utf-8'))
                # Set class on root element if it's a p tag
                if desc_root.tag == 'p':
                    desc_root.set('class', 'wpage_first_para')
                    description_html = XmlLib.element_to_string(desc_root)
                elif desc_root.tag == 'span':
                    # If it's a span, wrap in p with class
                    p_elem = fromstring('<p class="wpage_first_para"></p>')
                    p_elem.append(desc_root)
                    description_html = XmlLib.element_to_string(p_elem)
            except Exception as e:
                print(f"    Warning: Could not ensure wpage_first_para class: {e}")
        
        # Update entry with Wikipedia data
        entry_dict['wikipedia_url'] = getattr(wikipedia_page, 'url', None) or entry_dict.get('wikipedia_url', '')
        
        # Store definition and description separately
        if definition_html:
            entry_dict['definition_html'] = definition_html
        if description_html:
            entry_dict['description_html'] = description_html
        elif definition_html:
            # If only definition, use it as description too
            entry_dict['description_html'] = definition_html
        
        # Get Wikidata ID if available
        if not entry_dict.get('wikidata_id'):
            wikidata_id = _extract_wikidata_id_from_wikipedia_page(wikipedia_page)
            if wikidata_id:
                entry_dict['wikidata_id'] = wikidata_id
        
        print(f"  ✓ Added Wikipedia description for '{term}'")
        page_url = getattr(wikipedia_page, 'url', None) or entry_dict.get('wikipedia_url', 'N/A')
        print(f"    URL: {page_url}")
    else:
        # Wikipedia page retrieved but no paragraph extracted
        entry_dict['first_paragraph_retrieved'] = False
        print(f"  ⚠ No description extracted for '{term}'")
        print(f"    Page URL: {wikipedia_page.url if hasattr(wikipedia_page, 'url') else 'N/A'}")
        print(f"    Wikipedia page retrieved: ✓")
        print(f"    First paragraph retrieved: ✗")
        print(f"    This may indicate:")
        print(f"      - Page exists but has no readable first paragraph")
        print(f"      - Page is a disambiguation or redirect")
        print(f"      - Extraction method failed (check amilib version)")
        # Still save URL even if no description
        entry_dict['wikipedia_url'] = getattr(wikipedia_page, 'url', None) or entry_dict.get('wikipedia_url', '')
        # Clear any empty description_html that might exist
        if not entry_dict.get('description_html') or not _has_non_empty_description(entry_dict):
            entry_dict.pop('description_html', None)


def _extract_images_from_wikipedia_page(wikipedia_page, verbose: bool = False) -> List:
    """Extract images from WikipediaPage using amilib methods.
    
    Uses amilib's extract_a_elem_with_image_from_infobox() method first,
    then falls back to finding <figure> elements if no infobox image is found.
    This matches the strategy used by amilib's AmiEntry.add_figures_from_wikipedia().
    
    Args:
        wikipedia_page: WikipediaPage object
        verbose: If True, show detailed progress
        
    Returns:
        List of image elements (<a> tags or <figure> elements)
    """
    images = []
    
    # Step 1: Try to get <a> element with image from infobox
    img_elem = wikipedia_page.extract_a_elem_with_image_from_infobox()
    
    if img_elem is not None:
        images.append(img_elem)
        if verbose:
            print(f"    ✓ Found image via amilib extract_a_elem_with_image_from_infobox()")
    else:
        # Step 2: Fallback - look for <figure> elements if no infobox image
        if hasattr(wikipedia_page, 'html_elem') and wikipedia_page.html_elem is not None:
            figures = wikipedia_page.html_elem.xpath(".//figure")
            if len(figures) > 0:
                images.append(figures[0])
                if verbose:
                    print(f"    ✓ Found image via fallback <figure> element")
            elif verbose:
                print(f"    ⚠ No images found (no infobox image, no <figure> elements)")
        elif verbose:
            print(f"    ⚠ No images found (no infobox image, no html_elem available)")
    
    return images


def _fix_image_urls(element):
    """Fix relative image URLs to absolute Wikimedia URLs.
    
    Converts:
    - `/wiki/File:X.jpg` -> `https://en.wikipedia.org/wiki/File:X.jpg`
    - `//upload.wikimedia.org/...` -> `https://upload.wikimedia.org/...`
    - Relative paths -> Absolute Wikipedia URLs
    
    Args:
        element: lxml element containing images
    """
    wikipedia_base = "https://en.wikipedia.org"
    
    # Fix img src attributes (these point to actual image files)
    img_elements = element.xpath(".//img[@src]")
    for img in img_elements:
        src = img.get('src', '')
        if src:
            # Convert protocol-relative URL (//upload.wikimedia.org/...) to https://
            if src.startswith('//'):
                img.set('src', f"https:{src}")
            # Convert relative URL to absolute
            elif not src.startswith('http'):
                if src.startswith('/'):
                    # Absolute path on Wikipedia
                    img.set('src', f"{wikipedia_base}{src}")
                else:
                    # Relative path - prepend Wikipedia base
                    img.set('src', f"{wikipedia_base}/{src}")
        
        # Fix srcset attributes too (for responsive images)
        srcset = img.get('srcset', '')
        if srcset:
            # Replace // with https:// in srcset
            fixed_srcset = srcset.replace('//upload.wikimedia.org', 'https://upload.wikimedia.org')
            img.set('srcset', fixed_srcset)
    
    # Fix a href attributes that point to File: pages or Wikipedia pages
    a_elements = element.xpath(".//a[@href]")
    for a in a_elements:
        href = a.get('href', '')
        if href and not href.startswith('http'):
            # Convert protocol-relative URL
            if href.startswith('//'):
                a.set('href', f"https:{href}")
            # Convert relative Wikipedia URLs
            elif href.startswith('/'):
                a.set('href', f"{wikipedia_base}{href}")
            # Convert relative paths (wiki/File:, File:, etc.)
            elif 'File:' in href or href.startswith('wiki/'):
                if not href.startswith('/'):
                    href = '/' + href
                a.set('href', f"{wikipedia_base}{href}")


def add_images_feature(entry_dict: Dict, encyclopedia: AmiEncyclopedia, verbose: bool = False):
    """Add figures to entry from Wikipedia using _extract_images_from_wikipedia_page().
    
    Uses _extract_images_from_wikipedia_page() which calls amilib's 
    extract_a_elem_with_image_from_infobox() method to extract images.
    
    Args:
        entry_dict: Entry dictionary
        encyclopedia: Encyclopedia instance
        verbose: If True, show detailed progress
    """
    import copy
    
    term = entry_dict.get('term', entry_dict.get('canonical_term', ''))
    
    # Check if already has images or figure_html
    if entry_dict.get('images') or entry_dict.get('figure_html'):
        if verbose:
            print(f"  Entry '{term}' already has images")
        return
    
    # Get Wikipedia page
    if verbose:
        print(f"  Looking up Wikipedia page for '{term}' to extract images...")
    wikipedia_page = _get_wikipedia_page_for_entry(entry_dict)
    if not wikipedia_page:
        if verbose:
            print(f"  ⚠ Entry '{term}' has no Wikipedia page, skipping images")
        return
    
    page_url = getattr(wikipedia_page, 'url', None) or 'N/A'
    if verbose:
        print(f"  ✓ Wikipedia page retrieved: {page_url}")
    
    # Extract images using helper function
    if verbose:
        print(f"  Extracting images for '{term}' using amilib methods...")
    
    try:
        # Use _extract_images_from_wikipedia_page() helper function
        image_elements = _extract_images_from_wikipedia_page(wikipedia_page, verbose=verbose)
        
        if image_elements:
            # Use the first image element
            figure_elem = image_elements[0]
            
            try:
                # Fix relative URLs to absolute (ensure images load correctly)
                _fix_image_urls(figure_elem)
                
                # Store the figure element using copy.deepcopy()
                entry_dict['figure_html'] = copy.deepcopy(figure_elem)
                
                # Extract image_link URL for reference
                # Handle both <a> elements and <figure> elements
                image_url = None
                
                # Try to get href from <a> element (if figure_elem is an <a> tag)
                if hasattr(figure_elem, 'get') and hasattr(figure_elem, 'tag'):
                    if figure_elem.tag == 'a':
                        href = figure_elem.get('href', '')
                        if href:
                            # Ensure it's a full Wikipedia URL
                            if not href.startswith('http'):
                                if href.startswith('/wiki/File:') or href.startswith('/wiki/'):
                                    href = f"https://en.wikipedia.org{href}"
                                elif href.startswith('/'):
                                    href = f"https://en.wikipedia.org{href}"
                            image_url = href
                
                # If no href found, try to find img src in the element (works for both <a> and <figure>)
                if not image_url:
                    img_elem = figure_elem.xpath(".//img[@src]")
                    if img_elem:
                        img_src = img_elem[0].get('src', '')
                        if img_src:
                            image_url = img_src
                    else:
                        # For <figure> elements, also check for <a> tags inside
                        a_elem = figure_elem.xpath(".//a[@href]")
                        if a_elem:
                            href = a_elem[0].get('href', '')
                            if href:
                                if not href.startswith('http'):
                                    if href.startswith('/wiki/File:') or href.startswith('/wiki/'):
                                        href = f"https://en.wikipedia.org{href}"
                                    elif href.startswith('/'):
                                        href = f"https://en.wikipedia.org{href}"
                                image_url = href
                
                if image_url:
                    entry_dict['image_link'] = image_url
                
                if verbose:
                    print(f"  ✓ Added figure for '{term}'")
                    if entry_dict.get('image_link'):
                        print(f"    Link: {entry_dict['image_link']}")
            except Exception as e:
                # If we got an image element but failed to process it, still store it
                # This ensures figure_html is set even if URL fixing fails
                if 'figure_html' not in entry_dict:
                    entry_dict['figure_html'] = copy.deepcopy(figure_elem)
                if verbose:
                    print(f"  ⚠ Warning: Error processing image element for '{term}': {e}")
                    import traceback
                    traceback.print_exc()
        else:
            if verbose:
                print(f"  ⚠ No images found for '{term}'")
                
    except Exception as e:
        if verbose:
            print(f"  ⚠ Error extracting images for '{term}': {e}")
            import traceback
            traceback.print_exc()
        # Re-raise to ensure test failures are visible
        raise
