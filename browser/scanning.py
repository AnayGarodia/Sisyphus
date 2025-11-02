"""
Advanced scanning mixin for browser agent.
Intelligent element detection with scoring, persistent IDs, and smart filtering.
"""
from typing import Optional, Dict, List, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import hashlib
from .base_agent import console, action_logger, error_logger

@dataclass
class ElementData:
    """Rich element metadata with scoring."""
    stable_id: str
    index: int
    label: str
    type: str
    handle: object
    tag: str
    score: float
    href: Optional[str] = None
    parent_context: Optional[str] = None
    is_primary_action: bool = False
    metadata: Dict = field(default_factory=dict)

class ScanningMixin:
    """
    Advanced page scanning with intelligent element detection.
    Requires: self.page, self.element_map, self.log_action()
    """
    
    # Comprehensive selectors with priority
    SELECTORS = {
        'buttons': [
            'button',
            'input[type="button"]',
            'input[type="submit"]',
            '[role="button"]:not(a)',
            'a[role="button"]',
            '.btn',
            '[class*="button"]'
        ],
        'inputs': [
            'input[type="text"]',
            'input[type="email"]',
            'input[type="password"]',
            'input[type="search"]',
            'input[type="url"]',
            'input[type="tel"]',
            'textarea',
            '[contenteditable="true"]'
        ],
        'selects': [
            'select',
            '[role="listbox"]',
            '[role="combobox"]',
            '[role="menu"]',
            '.dropdown',
            '[class*="select"]'
        ],
        'checkboxes': [
            'input[type="checkbox"]',
            'input[type="radio"]',
            '[role="checkbox"]',
            '[role="radio"]'
        ],
        'links': [
            'a[href]:not([href="#"]):not([href=""]):not([href^="javascript:"])'
        ],
        'other_inputs': [
            'input[type="file"]',
            'input[type="number"]',
            'input[type="date"]',
            'input[type="time"]',
            'input[type="color"]',
            'input[type="range"]'
        ]
    }
    
    # Link importance scoring keywords
    IMPORTANT_LINK_KEYWORDS = {
        'navigation': ['home', 'about', 'contact', 'services', 'products', 'menu', 'login', 'signup', 'register'],
        'actions': ['create', 'new', 'add', 'edit', 'delete', 'save', 'submit', 'continue', 'next', 'start'],
        'content': ['article', 'post', 'page', 'category', 'section', 'view', 'read', 'more']
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._element_registry = {}  # stable_id -> ElementData
        self._next_index = 1
        self._scan_filters = []
    
    def scan(
        self, 
        filter_type: Optional[str] = None,
        max_elements: int = 50,
        min_score: float = 0.0,
        smart_mode: bool = True,
        include_dynamic: bool = True
    ) -> bool:
        """
        Advanced scan with intelligent filtering and scoring.
        
        Args:
            filter_type: Optional filter ('buttons', 'inputs', 'links', etc.) or 'all'
            max_elements: Maximum elements per type to display
            min_score: Minimum score threshold (0.0-1.0)
            smart_mode: Enable intelligent link filtering
            include_dynamic: Scan for dynamic/hidden elements
        
        Returns:
            True if scan succeeded
        """
        try:
            # Validate filter
            if filter_type and filter_type != 'all' and filter_type not in self.SELECTORS:
                console.print(f"[red]Unknown filter:[/red] {filter_type}")
                console.print(f"[dim]Available: {', '.join(self.SELECTORS.keys())}, all[/dim]")
                return False
            
            # Determine which types to scan
            if filter_type and filter_type != 'all':
                scan_types = [filter_type]
            else:
                scan_types = list(self.SELECTORS.keys())
            
            # Collect elements
            all_elements: List[ElementData] = []
            seen_stable_ids: Set[str] = set()
            
            for elem_type in scan_types:
                elements = self._scan_type(
                    elem_type, 
                    seen_stable_ids,
                    smart_mode=smart_mode and elem_type == 'links',
                    include_dynamic=include_dynamic
                )
                all_elements.extend(elements)
            
            # Apply score filtering
            if min_score > 0:
                all_elements = [e for e in all_elements if e.score >= min_score]
            
            # Intelligent sorting
            all_elements = self._smart_sort(all_elements, smart_mode)
            
            # Apply per-type limits intelligently
            all_elements = self._apply_smart_limits(all_elements, max_elements, scan_types)
            
            # Update element map (ADDITIVE, not replacement)
            self._update_element_map(all_elements)
            
            # Display results
            self._display_advanced_results(
                all_elements, 
                filter_type,
                min_score,
                smart_mode
            )
            
            self.log_action("scan", f"{len(all_elements)} elements (smart={smart_mode})", success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Scan failed:[/red] {e}")
            import traceback
            error_logger.debug(traceback.format_exc())
            self.log_action("scan", str(e), success=False)
            return False
    
    def _scan_type(
        self, 
        elem_type: str, 
        seen_ids: Set[str],
        smart_mode: bool = False,
        include_dynamic: bool = True
    ) -> List[ElementData]:
        """Scan for specific element type with advanced detection."""
        elements: List[ElementData] = []
        selectors = self.SELECTORS[elem_type]
        
        # Build combined selector
        combined_selector = ', '.join(selectors)
        
        try:
            found_elements = self.page.query_selector_all(combined_selector)
            
            # Also scan for dynamic elements if requested
            if include_dynamic:
                dynamic_elements = self._find_dynamic_elements(elem_type)
                found_elements.extend(dynamic_elements)
            
            for element in found_elements:
                try:
                    # Check visibility
                    is_visible = element.is_visible()
                    
                    # For some elements, check if they're in viewport or scrollable
                    if not is_visible:
                        is_visible = self._is_potentially_visible(element)
                    
                    if not is_visible:
                        continue
                    
                    # Generate stable ID
                    stable_id = self._generate_stable_id(element)
                    if stable_id in seen_ids:
                        continue
                    seen_ids.add(stable_id)
                    
                    # Extract metadata
                    tag = element.evaluate("el => el.tagName.toLowerCase()")
                    label = self._extract_advanced_label(element, tag)
                    
                    if not label or label.startswith("Unnamed"):
                        # For links, be more lenient
                        if elem_type != 'links':
                            continue
                    
                    display_type = self._classify_type(element, tag, elem_type)
                    
                    # Calculate relevance score
                    score = self._calculate_score(element, tag, label, display_type, smart_mode)
                    
                    # Extract additional metadata
                    href = None
                    parent_context = None
                    is_primary = False
                    
                    if tag == 'a':
                        href = element.get_attribute('href')
                        parent_context = self._get_parent_context(element)
                    
                    # Detect primary actions
                    is_primary = self._is_primary_action(element, label, display_type)
                    
                    # Get or assign persistent index
                    if stable_id in self._element_registry:
                        index = self._element_registry[stable_id].index
                    else:
                        index = self._next_index
                        self._next_index += 1
                    
                    elem_data = ElementData(
                        stable_id=stable_id,
                        index=index,
                        label=label,
                        type=display_type,
                        handle=element,
                        tag=tag,
                        score=score,
                        href=href,
                        parent_context=parent_context,
                        is_primary_action=is_primary
                    )
                    
                    elements.append(elem_data)
                    self._element_registry[stable_id] = elem_data
                    
                except Exception as e:
                    error_logger.debug(f"Skipped element in {elem_type}: {e}")
                    continue
        
        except Exception as e:
            error_logger.warning(f"Failed to scan {elem_type}: {e}")
        
        return elements
    
    def _find_dynamic_elements(self, elem_type: str) -> List:
        """Find hidden/dynamic elements that might appear on interaction."""
        dynamic_elements = []
        
        try:
            # Look for dropdown menus, hidden panels, etc.
            if elem_type in ['buttons', 'links']:
                # Find elements in hidden containers that might expand
                hidden_containers = self.page.query_selector_all(
                    '[style*="display: none"], [style*="visibility: hidden"], '
                    '[hidden], [aria-hidden="true"], .dropdown-menu, [role="menu"]'
                )
                
                for container in hidden_containers[:20]:  # Limit search
                    try:
                        # Check if container has show/expand mechanism
                        parent = container.evaluate(
                            "el => el.parentElement"
                        )
                        if parent:
                            # Find clickable elements within
                            inner_elements = container.query_selector_all(
                                'a[href], button, [role="button"], [role="menuitem"]'
                            )
                            dynamic_elements.extend(inner_elements)
                    except:
                        continue
        
        except Exception as e:
            error_logger.debug(f"Dynamic scan failed: {e}")
        
        return dynamic_elements
    
    def _is_potentially_visible(self, element) -> bool:
        """Check if element might become visible (in dropdown, scrollable area, etc.)."""
        try:
            result = element.evaluate("""
                el => {
                    // Check if in viewport or nearby
                    const rect = el.getBoundingClientRect();
                    const windowHeight = window.innerHeight || document.documentElement.clientHeight;
                    const windowWidth = window.innerWidth || document.documentElement.clientWidth;
                    
                    // Check if element has size
                    if (rect.width === 0 || rect.height === 0) return false;
                    
                    // Check if within reasonable scroll distance (3x viewport)
                    if (rect.top < windowHeight * 3 && rect.bottom > -windowHeight * 3) {
                        return true;
                    }
                    
                    // Check if parent might be expandable
                    let parent = el.parentElement;
                    while (parent) {
                        const style = window.getComputedStyle(parent);
                        if (style.display === 'none' || style.visibility === 'hidden') {
                            // Check if parent has show/expand classes or attributes
                            if (parent.classList.contains('dropdown') || 
                                parent.classList.contains('menu') ||
                                parent.hasAttribute('role') && parent.getAttribute('role').includes('menu')) {
                                return true;
                            }
                        }
                        parent = parent.parentElement;
                        if (parent === document.body) break;
                    }
                    
                    return false;
                }
            """)
            return result
        except:
            return False
    
    def _generate_stable_id(self, element) -> str:
        """Generate stable identifier for element across scans."""
        try:
            # Use combination of attributes that should remain stable
            identifier_data = element.evaluate("""
                el => {
                    const getPath = (el) => {
                        let path = [];
                        while (el && el.nodeType === Node.ELEMENT_NODE) {
                            let selector = el.nodeName.toLowerCase();
                            if (el.id) {
                                selector += '#' + el.id;
                                path.unshift(selector);
                                break;
                            } else {
                                let sibling = el;
                                let nth = 1;
                                while (sibling.previousElementSibling) {
                                    sibling = sibling.previousElementSibling;
                                    if (sibling.nodeName.toLowerCase() === selector) nth++;
                                }
                                if (nth > 1) selector += ':nth-of-type(' + nth + ')';
                                path.unshift(selector);
                            }
                            el = el.parentElement;
                            if (path.length > 5) break; // Limit depth
                        }
                        return path.join(' > ');
                    };
                    
                    return {
                        path: getPath(el),
                        text: el.innerText?.slice(0, 50) || '',
                        attrs: {
                            id: el.id || '',
                            name: el.getAttribute('name') || '',
                            class: el.className || '',
                            href: el.getAttribute('href') || '',
                            type: el.getAttribute('type') || ''
                        }
                    };
                }
            """)
            
            # Create hash from stable attributes
            hash_input = f"{identifier_data['path']}|{identifier_data['text']}|"
            hash_input += f"{identifier_data['attrs']['id']}|{identifier_data['attrs']['name']}"
            
            return hashlib.md5(hash_input.encode()).hexdigest()[:12]
            
        except Exception:
            # Fallback to simple hash
            return hashlib.md5(str(id(element)).encode()).hexdigest()[:12]
    
    def _extract_advanced_label(self, element, tag: str) -> str:
        """Extract meaningful label with advanced heuristics."""
        try:
            label_data = element.evaluate("""
                el => {
                    // Priority order for labels
                    const sources = {
                        ariaLabel: el.getAttribute('aria-label'),
                        ariaLabelledBy: (() => {
                            const id = el.getAttribute('aria-labelledby');
                            if (id) {
                                const labelEl = document.getElementById(id);
                                return labelEl ? labelEl.innerText : null;
                            }
                            return null;
                        })(),
                        placeholder: el.getAttribute('placeholder'),
                        title: el.getAttribute('title'),
                        value: el.getAttribute('value'),
                        text: el.innerText?.trim(),
                        alt: el.getAttribute('alt'),
                        name: el.getAttribute('name'),
                        id: el.getAttribute('id'),
                        // For links, try getting context
                        linkContext: (() => {
                            if (el.tagName.toLowerCase() === 'a') {
                                // Check parent for context
                                let parent = el.parentElement;
                                if (parent && parent.tagName.toLowerCase() === 'li') {
                                    return parent.innerText?.trim();
                                }
                            }
                            return null;
                        })(),
                        // For inputs, check associated label
                        labelFor: (() => {
                            if (el.id) {
                                const label = document.querySelector(`label[for="${el.id}"]`);
                                return label ? label.innerText : null;
                            }
                            const label = el.closest('label');
                            return label ? label.innerText : null;
                        })()
                    };
                    
                    return sources;
                }
            """)
            
            # Try each source in priority order
            for key in ['ariaLabel', 'ariaLabelledBy', 'labelFor', 'placeholder', 
                       'text', 'linkContext', 'title', 'alt', 'value', 'name', 'id']:
                label = label_data.get(key)
                if label and len(str(label).strip()) > 0:
                    label = ' '.join(str(label).split())  # Clean whitespace
                    
                    # For link text that's just URL, try to extract meaningful part
                    if key == 'text' and tag == 'a' and ('http' in label or '/' in label):
                        continue
                    
                    # Truncate long labels intelligently
                    if len(label) > 60:
                        label = label[:57] + "..."
                    
                    return label
            
            # Special handling for links with href but no text
            if tag == 'a':
                href = element.get_attribute("href") or ""
                if href and not href.startswith(('#', 'javascript:', 'mailto:')):
                    # Extract meaningful part from URL
                    url_label = self._extract_url_label(href)
                    if url_label:
                        return url_label
            
            return f"Unnamed {tag}"
            
        except Exception as e:
            error_logger.debug(f"Label extraction failed: {e}")
            return f"Unnamed {tag}"
    
    def _extract_url_label(self, href: str) -> Optional[str]:
        """Extract meaningful label from URL."""
        try:
            # Remove query params and fragments
            clean_url = href.split('?')[0].split('#')[0]
            
            # Get path parts
            parts = [p for p in clean_url.rstrip('/').split('/') if p]
            
            if not parts:
                return None
            
            # Get last meaningful part
            last_part = parts[-1]
            
            # Clean up common patterns
            last_part = last_part.replace('_', ' ').replace('-', ' ')
            
            # Capitalize
            last_part = ' '.join(word.capitalize() for word in last_part.split())
            
            if len(last_part) > 3:  # Minimum meaningful length
                return last_part[:60]
            
            return None
            
        except:
            return None
    
    def _get_parent_context(self, element) -> Optional[str]:
        """Get contextual information from parent elements."""
        try:
            context = element.evaluate("""
                el => {
                    let parent = el.parentElement;
                    let depth = 0;
                    while (parent && depth < 3) {
                        const tag = parent.tagName.toLowerCase();
                        if (tag === 'nav') return 'navigation';
                        if (tag === 'header') return 'header';
                        if (tag === 'footer') return 'footer';
                        if (tag === 'aside') return 'sidebar';
                        if (tag === 'article') return 'article';
                        
                        const role = parent.getAttribute('role');
                        if (role) return role;
                        
                        parent = parent.parentElement;
                        depth++;
                    }
                    return null;
                }
            """)
            return context
        except:
            return None
    
    def _calculate_score(
        self, 
        element, 
        tag: str, 
        label: str, 
        display_type: str,
        smart_mode: bool
    ) -> float:
        """Calculate relevance score for element (0.0 - 1.0)."""
        score = 0.5  # Base score
        
        try:
            # Type-based scoring
            type_scores = {
                'BUTTON': 0.8,
                'INPUT': 0.8,
                'SELECT': 0.7,
                'CHECKBOX': 0.6,
                'LINK': 0.4,  # Links start lower, boosted by content
                'OTHER': 0.3
            }
            score = type_scores.get(display_type, 0.5)
            
            # Primary action boost
            if self._is_primary_action(element, label, display_type):
                score += 0.2
            
            # Label quality boost
            if label and not label.startswith("Unnamed"):
                label_lower = label.lower()
                
                # Action words boost
                if smart_mode:
                    for category, keywords in self.IMPORTANT_LINK_KEYWORDS.items():
                        for keyword in keywords:
                            if keyword in label_lower:
                                score += 0.15
                                break
                
                # Clear, descriptive labels
                if len(label) > 5 and len(label) < 30:
                    score += 0.1
            
            # Accessibility boost
            if element.get_attribute('aria-label'):
                score += 0.1
            
            # Position boost (elements higher on page often more important)
            try:
                y_position = element.evaluate("""
                    el => el.getBoundingClientRect().top
                """)
                if y_position < 1000:  # First ~1000px
                    score += 0.1
            except:
                pass
            
            # Penalize navigation spam (same-domain links that are just "/")
            if tag == 'a' and smart_mode:
                href = element.get_attribute('href') or ''
                if href in ['/', '#', ''] or href.startswith('javascript:'):
                    score -= 0.3
            
            # Cap score
            return max(0.0, min(1.0, score))
            
        except Exception:
            return 0.5
    
    def _is_primary_action(self, element, label: str, display_type: str) -> bool:
        """Detect if element is a primary action."""
        try:
            if display_type not in ['BUTTON', 'LINK']:
                return False
            
            # Check classes/attributes
            primary_indicators = element.evaluate("""
                el => {
                    const classStr = el.className.toLowerCase();
                    const id = (el.id || '').toLowerCase();
                    return classStr.includes('primary') || 
                           classStr.includes('main') ||
                           classStr.includes('cta') ||
                           id.includes('primary');
                }
            """)
            
            if primary_indicators:
                return True
            
            # Check label for action words
            label_lower = label.lower()
            primary_words = ['submit', 'continue', 'next', 'create', 'sign up', 'register', 'buy', 'get started']
            if any(word in label_lower for word in primary_words):
                return True
            
            return False
            
        except:
            return False
    
    def _classify_type(self, element, tag: str, selector_type: str) -> str:
        """Determine display type for element."""
        if tag == 'a':
            return 'LINK'
        elif tag == 'button':
            return 'BUTTON'
        elif tag == 'select':
            return 'SELECT'
        elif tag == 'textarea':
            return 'INPUT'
        elif tag == 'input':
            input_type = element.get_attribute('type') or 'text'
            if input_type in ['checkbox', 'radio']:
                return 'CHECKBOX'
            elif input_type in ['button', 'submit', 'reset']:
                return 'BUTTON'
            else:
                return 'INPUT'
        elif element.get_attribute('role') == 'button':
            return 'BUTTON'
        else:
            return 'OTHER'
    
    def _smart_sort(self, elements: List[ElementData], smart_mode: bool) -> List[ElementData]:
        """Intelligently sort elements."""
        if smart_mode:
            # Sort by: primary actions first, then score, then type, then alphabetical
            elements.sort(key=lambda x: (
                -int(x.is_primary_action),  # Primary first (negative for reverse)
                -x.score,  # High score first
                {'BUTTON': 1, 'INPUT': 2, 'SELECT': 3, 'CHECKBOX': 4, 'LINK': 5, 'OTHER': 6}.get(x.type, 99),
                x.label.lower()
            ))
        else:
            # Standard sort
            type_order = {'BUTTON': 1, 'INPUT': 2, 'SELECT': 3, 'CHECKBOX': 4, 'LINK': 5, 'OTHER': 6}
            elements.sort(key=lambda x: (type_order.get(x.type, 99), x.label.lower()))
        
        return elements
    
    def _apply_smart_limits(
        self, 
        elements: List[ElementData], 
        max_per_type: int,
        scan_types: List[str]
    ) -> List[ElementData]:
        """Apply intelligent per-type limits."""
        if len(scan_types) == 1 and scan_types[0] != 'all':
            # Single type filter - just apply max
            return elements[:max_per_type]
        
        # Multiple types - apply per-type limits
        type_counts = defaultdict(int)
        filtered = []
        
        # Higher limits for important types
        type_limits = {
            'BUTTON': max_per_type,
            'INPUT': max_per_type,
            'SELECT': max_per_type // 2,
            'CHECKBOX': max_per_type // 2,
            'LINK': max_per_type * 2,  # Allow more links but they're scored lower
            'OTHER': max_per_type // 4
        }
        
        for elem in elements:
            limit = type_limits.get(elem.type, max_per_type)
            if type_counts[elem.type] < limit:
                filtered.append(elem)
                type_counts[elem.type] += 1
        
        return filtered
    
    def _update_element_map(self, elements: List[ElementData]):
        """Update element map ADDITIVELY (not replacement)."""
        for elem in elements:
            self.element_map[elem.index] = {
                'label': elem.label,
                'type': elem.type,
                'handle': elem.handle,
                'stable_id': elem.stable_id,
                'score': elem.score
            }
    
    def _display_advanced_results(
        self, 
        elements: List[ElementData],
        filter_type: Optional[str],
        min_score: float,
        smart_mode: bool
    ):
        """Display scan results with advanced formatting."""
        filter_text = f" ({filter_type})" if filter_type else ""
        mode_text = " [SMART]" if smart_mode else ""
        score_text = f" [scoreâ‰¥{min_score:.1f}]" if min_score > 0 else ""
        
        console.print(f"\n[bold cyan]SCAN RESULTS{filter_text}{mode_text}{score_text}[/bold cyan]")
        console.print("â”€" * 90)
        
        if not elements:
            console.print("[yellow]No interactive elements found[/yellow]")
            console.print("â”€" * 90)
            return
        
        # Group by type
        grouped: Dict[str, List[ElementData]] = defaultdict(list)
        for elem in elements:
            grouped[elem.type].append(elem)
        
        # Display each type group
        type_colors = {
            'BUTTON': 'green',
            'INPUT': 'yellow',
            'SELECT': 'magenta',
            'CHECKBOX': 'cyan',
            'LINK': 'blue',
            'OTHER': 'white'
        }
        
        for elem_type in ['BUTTON', 'INPUT', 'SELECT', 'CHECKBOX', 'LINK', 'OTHER']:
            if elem_type not in grouped:
                continue
            
            color = type_colors[elem_type]
            type_elements = grouped[elem_type]
            count = len(type_elements)
            
            console.print(f"\n[bold {color}]{elem_type}S ({count}):[/bold {color}]")
            
            for elem in type_elements:
                # Format with score and primary indicator
                score_str = f"{elem.score:.2f}"
                primary_marker = " â­" if elem.is_primary_action else ""
                
                if smart_mode:
                    console.print(
                        f"  [{elem.index:>3}] {elem.label} "
                        f"[dim]({score_str})[/dim]{primary_marker}"
                    )
                else:
                    console.print(f"  [{elem.index:>3}] {elem.label}")
        
        console.print("\n" + "â”€" * 90)
        console.print(f"[bold]Total: {len(elements)} elements[/bold] | Registry size: {len(self._element_registry)}")
        console.print(f"[dim]Use 'click N' or 'type N \"text\"' where N is the element number[/dim]")
        console.print(f"[dim]â­ = Primary action | Numbers persist across scans[/dim]\n")
    
    def rescan(self, preserve_map: bool = True) -> bool:
        """
        Rescan page with same settings.
        
        Args:
            preserve_map: Keep existing element indices
        
        Returns:
            True if rescan succeeded
        """
        if not preserve_map:
            self._element_registry.clear()
            self.element_map.clear()
            self._next_index = 1
        
        return self.scan()
    
    def clear_scan(self):
        """Clear all scan data and reset."""
        self._element_registry.clear()
        self.element_map.clear()
        self._next_index = 1
        console.print("[yellow]Scan data cleared[/yellow]")
    
    def get_element_info(self, selector: int) -> bool:
        """Display detailed information about a scanned element."""
        try:
            if selector not in self.element_map:
                console.print(f"[red]No element with index {selector}[/red]")
                console.print("[dim]Run 'scan' first[/dim]")
                return False
            
            meta = self.element_map[selector]
            element = meta['handle']
            
            # Gather comprehensive attributes
            attrs = element.evaluate("""
                el => {
                    const attrs = {};
                    for (let attr of el.attributes) {
                        attrs[attr.name] = attr.value;
                    }
                    
                    const rect = el.getBoundingClientRect();
                    
                    return {
                        tag: el.tagName.toLowerCase(),
                        text: el.innerText?.slice(0, 200),
                        visible: el.offsetParent !== null,
                        position: {
                            x: Math.round(rect.left),
                            y: Math.round(rect.top),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        },
                        computed: {
                            display: window.getComputedStyle(el).display,
                            visibility: window.getComputedStyle(el).visibility,
                            zIndex: window.getComputedStyle(el).zIndex
                        },
                        attrs: attrs
                    };
                }
            """)
            
            console.print(f"\n[bold cyan]Element [{selector}] Detailed Info:[/bold cyan]")
            console.print("â”€" * 70)
            console.print(f"  [bold]Label:[/bold]   {meta['label']}")
            console.print(f"  [bold]Type:[/bold]    {meta['type']}")
            console.print(f"  [bold]Tag:[/bold]     <{attrs['tag']}>")
            console.print(f"  [bold]Score:[/bold]   {meta.get('score', 0.0):.2f}")
            console.print(f"  [bold]ID:[/bold]      {meta.get('stable_id', 'N/A')}")
            console.print(f"  [bold]Visible:[/bold] {attrs['visible']}")
            
            # Position info
            pos = attrs['position']
            console.print(f"\n  [bold]Position:[/bold]")
            console.print(f"    Location: ({pos['x']}, {pos['y']})")
            console.print(f"    Size: {pos['width']}x{pos['height']}px")
            
            # Display computed styles
            comp = attrs['computed']
            console.print(f"\n  [bold]Computed Styles:[/bold]")
            console.print(f"    Display: {comp['display']}")
            console.print(f"    Visibility: {comp['visibility']}")
            console.print(f"    Z-Index: {comp['zIndex']}")
            
            # Text content
            if attrs.get('text'):
                console.print(f"\n  [bold]Text Content:[/bold]")
                console.print(f"    {attrs['text'][:150]}")
            
            # Attributes
            if attrs['attrs']:
                console.print(f"\n  [bold]Attributes:[/bold]")
                important_attrs = ['id', 'name', 'class', 'href', 'type', 'value', 
                                 'placeholder', 'aria-label', 'role']
                
                for key in important_attrs:
                    if key in attrs['attrs']:
                        val = attrs['attrs'][key]
                        if val:
                            display_val = val[:60] + "..." if len(val) > 60 else val
                            console.print(f"    {key}: {display_val}")
                
                # Show remaining attributes
                other_attrs = {k: v for k, v in attrs['attrs'].items() 
                             if k not in important_attrs and v}
                if other_attrs:
                    console.print(f"\n  [bold]Other Attributes:[/bold]")
                    for key, val in list(other_attrs.items())[:5]:
                        display_val = val[:40] + "..." if len(val) > 40 else val
                        console.print(f"    {key}: {display_val}")
            
            console.print("\n" + "â”€" * 70 + "\n")
            
            self.log_action("element_info", f"[{selector}] {meta['label']}", success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Failed to get element info:[/red] {e}")
            import traceback
            error_logger.debug(traceback.format_exc())
            self.log_action("element_info", str(e), success=False)
            return False
    
    def scan_smart(self, element_type: str = 'all', limit: int = 30) -> bool:
        """
        Quick smart scan with intelligent defaults.
        
        Args:
            element_type: Type to scan ('all', 'buttons', 'inputs', 'links')
            limit: Max elements to show
        
        Returns:
            True if succeeded
        """
        return self.scan(
            filter_type=element_type,
            max_elements=limit,
            min_score=0.3,  # Filter low-value elements
            smart_mode=True,
            include_dynamic=True
        )
    
    def scan_all(self, limit: int = 100) -> bool:
        """
        Comprehensive scan with minimal filtering.
        
        Args:
            limit: Max elements per type
        
        Returns:
            True if succeeded
        """
        return self.scan(
            filter_type='all',
            max_elements=limit,
            min_score=0.0,
            smart_mode=False,
            include_dynamic=True
        )
    
    def find_elements(self, search_term: str, type_filter: Optional[str] = None) -> bool:
        """
        Search for elements by label text.
        
        Args:
            search_term: Text to search for in labels
            type_filter: Optional type filter
        
        Returns:
            True if found any matches
        """
        search_lower = search_term.lower()
        matches = []
        
        for idx, meta in self.element_map.items():
            if type_filter and meta['type'] != type_filter.upper():
                continue
            
            if search_lower in meta['label'].lower():
                matches.append((idx, meta))
        
        if not matches:
            console.print(f"[yellow]No elements found matching '{search_term}'[/yellow]")
            if type_filter:
                console.print(f"[dim]Filter: {type_filter}[/dim]")
            console.print("[dim]Try running 'scan' first or use different search term[/dim]")
            return False
        
        console.print(f"\n[bold cyan]Found {len(matches)} matching elements:[/bold cyan]")
        console.print("â”€" * 70)
        
        for idx, meta in matches:
            score_info = f" ({meta['score']:.2f})" if 'score' in meta else ""
            console.print(f"  [{idx:>3}] {meta['type']:<10} {meta['label']}{score_info}")
        
        console.print("â”€" * 70 + "\n")
        
        self.log_action("find", f"'{search_term}' -> {len(matches)} results", success=True)
        return True
    
    def list_elements(self, element_type: Optional[str] = None) -> bool:
        """
        List all currently mapped elements.
        
        Args:
            element_type: Optional filter by type
        
        Returns:
            True if listed successfully
        """
        if not self.element_map:
            console.print("[yellow]No elements in map. Run 'scan' first.[/yellow]")
            return False
        
        elements_to_show = []
        
        for idx, meta in sorted(self.element_map.items()):
            if element_type and meta['type'] != element_type.upper():
                continue
            elements_to_show.append((idx, meta))
        
        if not elements_to_show:
            console.print(f"[yellow]No {element_type} elements in map[/yellow]")
            return False
        
        type_text = f" ({element_type})" if element_type else ""
        console.print(f"\n[bold cyan]Current Element Map{type_text}:[/bold cyan]")
        console.print("â”€" * 70)
        
        # Group by type
        grouped = defaultdict(list)
        for idx, meta in elements_to_show:
            grouped[meta['type']].append((idx, meta))
        
        type_colors = {
            'BUTTON': 'green',
            'INPUT': 'yellow',
            'SELECT': 'magenta',
            'CHECKBOX': 'cyan',
            'LINK': 'blue',
            'OTHER': 'white'
        }
        
        for elem_type in ['BUTTON', 'INPUT', 'SELECT', 'CHECKBOX', 'LINK', 'OTHER']:
            if elem_type not in grouped:
                continue
            
            color = type_colors[elem_type]
            console.print(f"\n[bold {color}]{elem_type}S ({len(grouped[elem_type])}):[/bold {color}]")
            
            for idx, meta in grouped[elem_type]:
                console.print(f"  [{idx:>3}] {meta['label']}")
        
        console.print("\n" + "â”€" * 70)
        console.print(f"[bold]Total: {len(elements_to_show)} elements[/bold]\n")
        
        return True
    
    def get_stats(self) -> Dict:
        """Get scanning statistics."""
        stats = {
            'total_elements': len(self.element_map),
            'registry_size': len(self._element_registry),
            'next_index': self._next_index,
            'types': defaultdict(int)
        }
        
        for meta in self.element_map.values():
            stats['types'][meta['type']] += 1
        
        return dict(stats)
    
    def print_stats(self):
        """Print scanning statistics."""
        stats = self.get_stats()
        
        console.print("\n[bold cyan]Scanning Statistics:[/bold cyan]")
        console.print("â”€" * 50)
        console.print(f"  Total Mapped Elements: {stats['total_elements']}")
        console.print(f"  Registry Size: {stats['registry_size']}")
        console.print(f"  Next Available Index: {stats['next_index']}")
        
        if stats['types']:
            console.print("\n  [bold]Elements by Type:[/bold]")
            for elem_type, count in sorted(stats['types'].items()):
                console.print(f"    {elem_type}: {count}")
        
        console.print("â”€" * 50 + "\n")

    # ==================== NEW: Page Information ====================
    
    def screenshot(self, filename: str = None) -> bool:
        """
        Take a full page screenshot.
        
        Args:
            filename: Optional filename (auto-generated from URL if not provided)
        
        Returns:
            True if screenshot succeeded
        """
        try:
            import os
            import re
            from datetime import datetime
            from urllib.parse import urlparse
            
            # Create screenshots folder
            screenshots_dir = "screenshots"
            if not os.path.exists(screenshots_dir):
                os.makedirs(screenshots_dir)
            
            # Generate filename from URL if not provided
            if filename is None:
                current_url = self.page.url
                parsed_url = urlparse(current_url)
                domain = parsed_url.netloc.replace('www.', '')
                path = parsed_url.path.strip('/')
                
                # Clean filename
                clean_domain = re.sub(r'[^\w\-]', '_', domain)
                clean_path = re.sub(r'[^\w\-]', '_', path) if path else 'home'
                
                # Add timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                if clean_path and clean_path != 'home':
                    filename = f"{clean_domain}_{clean_path}_{timestamp}.png"
                else:
                    filename = f"{clean_domain}_{timestamp}.png"
            elif not filename.endswith('.png'):
                filename += '.png'
            
            # Full path
            filepath = os.path.join(screenshots_dir, filename)
            
            # Take screenshot
            self.page.screenshot(path=filepath, full_page=True)
            
            console.print(f"[green]âœ“ Screenshot saved:[/green] {filepath}")
            self.log_action("screenshot", filepath, success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Screenshot failed:[/red] {e}")
            self.log_action("screenshot", str(e), success=False)
            return False
    
    def read_page(self, focus: str = "overview", save: bool = False, max_chars: int = 1500) -> str:
        """
        Extract page content with intelligent filtering.
        
        Args:
            focus: What to extract
                - "overview" - Title, headings, key paragraphs (default, max 1500 chars)
                - "content" - Full article/text content (max 1500 chars)
                - "forms" - Form fields, labels, inputs, buttons
                - "navigation" - Menus, links, site structure
                - "all" - Everything (max 1500 chars unless specified)
            save: Whether to save to file (default False)
            max_chars: Maximum characters to return (default 1500, prevents token overflow)
        
        Returns:
            Extracted text as string (guaranteed <= max_chars)
        """
        try:
            import os
            import re
            from datetime import datetime
            
            # JavaScript extraction
            content_data = self.page.evaluate(f"""
                (focus) => {{
                    const result = {{
                        title: document.title || 'Untitled',
                        url: window.location.href,
                        focus: focus,
                        sections: []
                    }};
                    
                    const getImportance = (element) => {{
                        let score = 0;
                        const tag = element.tagName.toLowerCase();
                        
                        if (/^h[1-6]$/.test(tag)) score = 10 - parseInt(tag[1]);
                        if (element.closest('main, article, [role="main"]')) score += 5;
                        if (tag === 'form' || tag === 'input' || tag === 'textarea') score += 8;
                        if (element.closest('form')) score += 3;
                        
                        const rect = element.getBoundingClientRect();
                        if (rect.top < 500) score += 2;
                        
                        const text = element.innerText?.trim() || '';
                        if (text.length > 100 && text.length < 500) score += 2;
                        if (text.length > 500) score += 1;
                        
                        return score;
                    }};
                    
                    const mainArea = document.querySelector('main, article, [role="main"]') || document.body;
                    
                    if (focus === 'forms') {{
                        const forms = Array.from(document.querySelectorAll('form, input, textarea, select, button'));
                        const formData = forms.map(el => {{
                            const label = el.labels?.[0]?.innerText || 
                                        el.getAttribute('placeholder') || 
                                        el.getAttribute('aria-label') || 
                                        el.name || 'unlabeled';
                            return {{
                                type: el.tagName.toLowerCase(),
                                label: label.substring(0, 100),
                                importance: 10
                            }};
                        }});
                        
                        result.sections = [{{
                            level: 1,
                            title: 'Form Elements',
                            content: formData.map(f => `[${{f.type}}] ${{f.label}}`),
                            importance: 10
                        }}];
                        
                    }} else if (focus === 'navigation') {{
                        const navs = Array.from(document.querySelectorAll('nav, [role="navigation"], header'));
                        const links = navs.flatMap(nav => 
                            Array.from(nav.querySelectorAll('a')).map(a => a.innerText.trim())
                        ).filter(t => t.length > 0 && t.length < 50);
                        
                        result.sections = [{{
                            level: 1,
                            title: 'Navigation',
                            content: links,
                            importance: 8
                        }}];
                        
                    }} else {{
                        const sections = [];
                        let currentSection = null;
                        
                        const elements = Array.from(mainArea.querySelectorAll('h1, h2, h3, h4, h5, h6, p, div, ul, ol, blockquote, article, section'));
                        
                        const contentElements = elements.filter(el => {{
                            if (el.closest('nav, header, footer, .ad, [role="navigation"], aside')) return false;
                            
                            const tag = el.tagName.toLowerCase();
                            if (/^h[1-6]$/.test(tag)) return el.innerText.trim().length > 0;
                            
                            return (el.innerText?.trim() || '').length >= 10;
                        }});
                        
                        const processedElements = new Set();
                        
                        for (const el of contentElements) {{
                            if (processedElements.has(el)) continue;
                            
                            const tagName = el.tagName.toLowerCase();
                            const importance = getImportance(el);
                            
                            if (/^h[1-6]$/.test(tagName)) {{
                                const level = parseInt(tagName[1]);
                                const text = el.innerText.trim();
                                
                                if (text.length > 0) {{
                                    currentSection = {{
                                        level: level,
                                        title: text,
                                        content: [],
                                        importance: importance
                                    }};
                                    sections.push(currentSection);
                                    processedElements.add(el);
                                }}
                            }} else {{
                                let text = el.innerText.trim();
                                
                                const children = Array.from(el.querySelectorAll('*'));
                                if (children.some(child => processedElements.has(child))) continue;
                                
                                if (text.length >= 10) {{
                                    if (!currentSection) {{
                                        currentSection = {{
                                            level: 1,
                                            title: 'Content',
                                            content: [],
                                            importance: 5
                                        }};
                                        sections.push(currentSection);
                                    }}
                                    
                                    currentSection.content.push({{
                                        text: text,
                                        importance: importance
                                    }});
                                    
                                    processedElements.add(el);
                                    children.forEach(child => processedElements.add(child));
                                }}
                            }}
                        }}
                        
                        if (focus === 'overview') {{
                            sections.sort((a, b) => b.importance - a.importance);
                        }}
                        
                        result.sections = sections;
                    }}
                    
                    return result;
                }}
            """, focus)
            
            if not content_data or len(content_data.get('sections', [])) == 0:
                console.print("[yellow]No content found[/yellow]")
                return "No content found on page"
            
            # Build markdown
            lines = []
            lines.append(f"# {content_data['title']}\n\n")
            lines.append(f"**Source:** {content_data['url']}\n")
            lines.append(f"**Focus:** {focus}\n")
            lines.append(f"**Extracted:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            lines.append("---\n\n")
            
            total_chars = 0
            sections_included = 0
            
            # Build content up to max_chars limit
            for section in content_data['sections']:
                if focus == "overview" and section.get('importance', 0) < 5:
                    continue
                
                # Stop if we're approaching the limit
                if total_chars > max_chars - 200:  # Leave room for truncation message
                    break
                
                level = section['level']
                title = section['title']
                content = section['content']
                
                lines.append(f"{'#' * level} {title}\n\n")
                
                for item in content:
                    # Check limit before adding each item
                    if total_chars > max_chars - 200:
                        break
                    
                    if isinstance(item, dict):
                        text = item['text']
                        importance = item.get('importance', 0)
                        
                        if focus == "overview" and importance < 3:
                            continue
                    else:
                        text = item
                    
                    if len(text.strip()) >= 10:
                        clean = ' '.join(text.split())
                        lines.append(f"{clean}\n\n")
                        total_chars += len(clean)
                
                sections_included += 1
            
            result_text = ''.join(lines)
            
            # HARD LIMIT - truncate if still too long
            if len(result_text) > max_chars:
                result_text = result_text[:max_chars]
                result_text += f"\n\n*[Truncated at {max_chars} chars to prevent token overflow]*"
            
            # Optional file save (save FULL content, not truncated)
            if save:
                exports_dir = "text_exports"
                if not os.path.exists(exports_dir):
                    os.makedirs(exports_dir)
                
                url_clean = re.sub(r'^https?://', '', content_data['url'])
                url_clean = re.sub(r'[^\w\-_.]', '_', url_clean)
                url_clean = re.sub(r'_+', '_', url_clean).strip('_')[:100]
                
                filename = f"{url_clean}_{focus}.md"
                filepath = os.path.join(exports_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(result_text)
                
                console.print(f"[green]âœ“ Saved:[/green] {filepath}")
            
            console.print(f"[green]âœ“ Extracted {len(result_text)} chars ({sections_included} sections)[/green]")
            self.log_action("read_page", f"{focus} - {len(result_text)} chars", success=True)
            
            return result_text
            
        except Exception as e:
            console.print(f"[red]Failed to read page:[/red] {e}")
            import traceback
            error_logger.debug(traceback.format_exc())
            self.log_action("read_page", str(e), success=False)
            return f"Error reading page: {e}"