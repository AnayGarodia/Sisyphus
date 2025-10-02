"""
Scanning mixin for browser agent.
Detects and maps interactive elements on the page.
"""

from typing import Optional, Dict, List
from .base_agent import console, action_logger, error_logger


class ScanningMixin:
    """
    Page scanning and element detection.
    Requires: self.page, self.element_map, self.log_action()
    """
    
    # Element type selectors (prioritized)
    SELECTORS = {
        'buttons': 'button, input[type="button"], input[type="submit"], [role="button"]:not(a)',
        'inputs': 'input[type="text"], input[type="email"], input[type="password"], input[type="search"], input[type="url"], textarea',
        'selects': 'select, [role="listbox"], [role="combobox"]',
        'checkboxes': 'input[type="checkbox"], input[type="radio"]',
        'links': 'a[href]:not([href="#"]):not([href=""]):not([href^="javascript:"])',
        'other_inputs': 'input[type="file"], input[type="number"], input[type="date"], input[type="tel"], input[type="time"]'
    }
    
    def scan(self, filter_type: Optional[str] = None, max_elements: int = 50) -> bool:
        """
        Scan page for interactive elements and build element map.
        
        Args:
            filter_type: Optional filter ('buttons', 'inputs', 'links', etc.)
            max_elements: Maximum elements to display (prevents spam)
        
        Returns:
            True if scan succeeded
        """
        try:
            # Filter selectors if requested
            if filter_type:
                if filter_type not in self.SELECTORS:
                    console.print(f"[red]Unknown filter:[/red] {filter_type}")
                    console.print(f"[dim]Available: {', '.join(self.SELECTORS.keys())}[/dim]")
                    return False
                selectors = {filter_type: self.SELECTORS[filter_type]}
            else:
                selectors = self.SELECTORS
            
            # Clear previous map
            self.element_map = {}
            all_elements = []
            seen_handles = set()
            
            # Scan each selector type
            for elem_type, selector in selectors.items():
                elements = self.page.query_selector_all(selector)
                
                for element in elements:
                    try:
                        # Skip invisible elements
                        if not element.is_visible():
                            continue
                        
                        # Prevent duplicates (same element matched by multiple selectors)
                        handle_id = id(element)
                        if handle_id in seen_handles:
                            continue
                        seen_handles.add(handle_id)
                        
                        # Get metadata
                        tag = element.evaluate("el => el.tagName.toLowerCase()")
                        label = self._extract_label(element, tag)
                        
                        if not label or label == f"Unnamed {tag}":
                            continue  # Skip elements without useful labels
                        
                        display_type = self._classify_type(element, tag, elem_type)
                        
                        all_elements.append({
                            'label': label,
                            'type': display_type,
                            'handle': element,
                            'tag': tag
                        })
                        
                    except Exception as e:
                        error_logger.debug(f"Skipped element: {e}")
                        continue
            
            # Sort by type priority, then alphabetically
            type_order = {'BUTTON': 1, 'INPUT': 2, 'SELECT': 3, 'CHECKBOX': 4, 'LINK': 5, 'OTHER': 6}
            all_elements.sort(key=lambda x: (type_order.get(x['type'], 99), x['label'].lower()))
            
            # Truncate if needed
            truncated = len(all_elements) > max_elements
            if truncated:
                all_elements = all_elements[:max_elements]
            
            # Build element map
            for idx, elem in enumerate(all_elements, start=1):
                self.element_map[idx] = {
                    'label': elem['label'],
                    'type': elem['type'],
                    'handle': elem['handle']
                }
            
            # Display results
            self._display_scan_results(all_elements, truncated, filter_type)
            
            self.log_action("scan", f"{len(all_elements)} elements", success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Scan failed:[/red] {e}")
            self.log_action("scan", str(e), success=False)
            return False
    
    def _extract_label(self, element, tag: str) -> str:
        """
        Extract meaningful label for element.
        Priority: aria-label > placeholder > text > title > value > name > id > generic
        """
        try:
            # Try label sources in priority order
            label_getters = [
                lambda: element.get_attribute("aria-label"),
                lambda: element.get_attribute("placeholder"),
                lambda: element.inner_text().strip()[:60] if element.inner_text() else None,
                lambda: element.get_attribute("title"),
                lambda: element.get_attribute("value"),
                lambda: element.get_attribute("name"),
                lambda: element.get_attribute("id"),
            ]
            
            for getter in label_getters:
                try:
                    label = getter()
                    if label and len(label.strip()) > 0:
                        # Clean whitespace
                        label = ' '.join(label.split())
                        
                        # Truncate long labels
                        if len(label) > 60:
                            label = label[:57] + "..."
                        
                        return label
                except:
                    continue
            
            # Special case: links with href but no text
            if tag == 'a':
                href = element.get_attribute("href") or ""
                if href and not href.startswith(('#', 'javascript:', 'mailto:')):
                    # Extract last path segment or domain
                    parts = href.rstrip('/').split('/')
                    return parts[-1] if parts[-1] else parts[-2] if len(parts) > 1 else href[:60]
            
            # Fallback: try parent label
            try:
                parent_label = element.evaluate("""
                    el => {
                        const label = el.closest('label') || 
                                     document.querySelector(`label[for="${el.id}"]`);
                        return label ? label.innerText.trim() : '';
                    }
                """)
                if parent_label:
                    return parent_label[:60]
            except:
                pass
            
            # Generic fallback
            return f"Unnamed {tag}"
            
        except Exception:
            return f"Unnamed {tag}"
    
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
    
    def _display_scan_results(self, elements: List[Dict], truncated: bool, filter_type: Optional[str]):
        """Display scan results in clean grouped format."""
        filter_text = f" ({filter_type})" if filter_type else ""
        
        console.print(f"\n[bold cyan]SCAN RESULTS{filter_text}[/bold cyan]")
        console.print("─" * 80)
        
        if not elements:
            console.print("[yellow]No interactive elements found[/yellow]")
            console.print("─" * 80)
            return
        
        # Group by type
        grouped: Dict[str, List[tuple]] = {}
        for idx, elem in enumerate(elements, start=1):
            elem_type = elem['type']
            if elem_type not in grouped:
                grouped[elem_type] = []
            grouped[elem_type].append((idx, elem['label']))
        
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
            count = len(grouped[elem_type])
            
            console.print(f"\n[bold {color}]{elem_type}S ({count}):[/bold {color}]")
            
            for idx, label in grouped[elem_type]:
                console.print(f"  [{idx:>3}] {label}")
        
        console.print("\n" + "─" * 80)
        
        if truncated:
            console.print(f"[yellow]Showing first {len(elements)} elements[/yellow]")
        
        console.print(f"[dim]Use 'click N' or 'type N \"text\"' where N is the element number[/dim]\n")
    
    def get_element_info(self, selector: int) -> bool:
        """
        Display detailed information about a scanned element.
        
        Args:
            selector: Element index from scan
        
        Returns:
            True if info displayed
        """
        try:
            if selector not in self.element_map:
                console.print(f"[red]No element with index {selector}[/red]")
                console.print("[dim]Run 'scan' first[/dim]")
                return False
            
            meta = self.element_map[selector]
            element = meta['handle']
            
            # Gather attributes
            attrs = element.evaluate("""
                el => {
                    const attrs = {};
                    for (let attr of el.attributes) {
                        attrs[attr.name] = attr.value;
                    }
                    return {
                        tag: el.tagName.toLowerCase(),
                        text: el.innerText?.slice(0, 100),
                        visible: el.offsetParent !== null,
                        attrs: attrs
                    };
                }
            """)
            
            console.print(f"\n[bold cyan]Element [{selector}] Info:[/bold cyan]")
            console.print(f"  Label:   {meta['label']}")
            console.print(f"  Type:    {meta['type']}")
            console.print(f"  Tag:     <{attrs['tag']}>")
            console.print(f"  Visible: {attrs['visible']}")
            
            if attrs.get('text'):
                console.print(f"  Text:    {attrs['text']}")
            
            if attrs['attrs']:
                console.print("\n  Attributes:")
                for key, val in list(attrs['attrs'].items())[:10]:  # Limit output
                    console.print(f"    {key}={val[:50]}")
            
            console.print()
            
            self.log_action("element_info", f"[{selector}] {meta['label']}", success=True)
            return True
            
        except Exception as e:
            console.print(f"[red]Failed to get element info:[/red] {e}")
            self.log_action("element_info", str(e), success=False)
            return False