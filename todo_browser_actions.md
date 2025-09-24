Core Browser Control - ANAY

type <selector> <text> - Type text into field
press <key> - Press keyboard key (Enter, Tab, Esc, etc.)
key_combo <keys> - Key combinations (Ctrl+C, Alt+Tab)
fill <selector> <text> - Fill form field
clear <selector> - Clear input field
select <selector> <option> - Select dropdown option
check <selector> - Check checkbox/radio button
uncheck <selector> - Uncheck checkbox
toggle <selector> - Toggle checkbox state
submit <selector> - Submit form
focus <selector> - Focus on element
blur <selector> - Remove focus from element
drag <from> <to> - Drag and drop elements
upload <selector> <file> - Upload file
download <url> [filename] - Download file

Navigation & Page Control - PRATYUSH

hard_refresh - Force reload (Ctrl+F5) #Not Working

Scrolling & Movement - PRATYUSH

scroll_to <selector> - Scroll to element #Not Working
page_up - Page up #Need to Increase Magnitude
page_down - Page down #Need to Increase Magnitude
hover <selector> - Mouse hover #Not Working

Element Discovery & Inspection

find <text> - Find text on page
find_all <selector> - Find all matching elements
list <type> - List elements (buttons, links, inputs)
count <selector> - Count matching elements
exists <selector> - Check if element exists
visible <selector> - Check if element visible
enabled <selector> - Check if element enabled
selected <selector> - Check if option selected
checked <selector> - Check if checkbox checked
text <selector> - Get element text
html <selector> - Get element HTML
value <selector> - Get input value
attribute <selector> <attr> - Get attribute value
css <selector> <property> - Get CSS property
position <selector> - Get element coordinates
size <selector> - Get element dimensions
bounds <selector> - Get element bounding box

Page Content & Source

source - Get page HTML
text_all - Get all visible text
links - Get all links on page
images - Get all images on page
forms - Get all forms on page
tables - Get all tables on page
meta <name> - Get meta tag content
lang - Get page language
encoding - Get page encoding
doctype - Get document type

Screenshots & Media

screenshot [filename] - Full page screenshot
screenshot_element <selector> - Element screenshot
pdf [filename] - Save as PDF
print - Print page
record_video - Start video recording
stop_video - Stop video recording
record_gif - Record animated GIF

Multi-Tab Management

new_tab [url] - Open new tab
close_tab - Close current tab
close_other_tabs - Close all other tabs
duplicate_tab - Duplicate current tab
switch_tab <index> - Switch to tab
next_tab - Switch to next tab
prev_tab - Switch to previous tab
tabs - List all tabs
pin_tab - Pin current tab
unpin_tab - Unpin current tab
mute_tab - Mute tab audio
unmute_tab - Unmute tab

Window Management

new_window [url] - Open new window
close_window - Close current window
switch_window <index> - Switch window
windows - List all windows
minimize - Minimize window
maximize - Maximize window
fullscreen - Toggle fullscreen
size <width> <height> - Set window size
position <x> <y> - Set window position
center_window - Center window on screen

Cookies & Storage

cookies - Get all cookies
get_cookie <name> - Get specific cookie
set_cookie <name> <value> - Set cookie
delete_cookie <name> - Delete cookie
clear_cookies - Clear all cookies
local_storage - Get local storage data
set_local <key> <value> - Set local storage
session_storage - Get session storage
clear_storage - Clear all storage

JavaScript Execution

execute <code> - Run JavaScript
evaluate <expression> - Evaluate JS expression
inject_script <file> - Inject JS file
console_log - Get console messages
console_clear - Clear console
alert <message> - Show alert dialog
confirm <message> - Show confirm dialog
prompt <message> - Show prompt dialog

Network & Requests

requests - Show network requests
clear_requests - Clear request log
block <pattern> - Block network requests
unblock <pattern> - Unblock requests
intercept <pattern> - Intercept requests
modify_request <pattern> - Modify requests
response <url> - Get response details
headers - Get response headers
status_code - Get HTTP status code
redirect_chain - Get redirect history

Performance & Metrics

performance - Get performance metrics
load_time - Get page load time
dom_ready_time - Get DOM ready time
first_paint - Get first paint time
lighthouse - Run Lighthouse audit
coverage - Get code coverage
memory - Get memory usage
cpu - Get CPU usage

Browser Settings & Configuration

user_agent <string> - Set user agent
viewport <width> <height> - Set viewport size
device <name> - Emulate device
mobile - Switch to mobile mode
desktop - Switch to desktop mode
orientation <mode> - Set orientation
zoom <level> - Set zoom level
geolocation <lat> <lon> - Set location
timezone <tz> - Set timezone
locale <lang> - Set language
permissions <type> <state> - Manage permissions
offline - Go offline
online - Go online
throttle <speed> - Throttle network
media_type <type> - Set media type (print/screen)

Authentication & Security

basic_auth <user> <pass> - HTTP basic auth
bearer_token <token> - Set bearer token
client_cert <cert> - Set client certificate
ignore_cert_errors - Ignore SSL errors
security_details - Get security info
mixed_content - Check mixed content

Forms & Input Validation

form_data <selector> - Get form data
validate_form <selector> - Validate form
reset_form <selector> - Reset form
autocomplete <selector> - Trigger autocomplete
datalist <selector> - Get datalist options
form_errors - Get form validation errors

Advanced Element Interaction

select_text <selector> - Select text in element
copy_text <selector> - Copy element text
paste <selector> - Paste clipboard content
context_menu <selector> - Open context menu
tooltip <selector> - Get tooltip text
placeholder <selector> - Get placeholder text
readonly <selector> - Check if readonly
required <selector> - Check if required

Testing & Assertions

assert_text <text> - Assert text exists
assert_not_text <text> - Assert text doesn't exist
assert_url <url> - Assert current URL
assert_title <title> - Assert page title
assert_visible <selector> - Assert element visible
assert_hidden <selector> - Assert element hidden
assert_enabled <selector> - Assert element enabled
assert_disabled <selector> - Assert element disabled
assert_checked <selector> - Assert checkbox checked
assert_value <selector> <value> - Assert input value
assert_count <selector> <num> - Assert element count

Waiting & Timing

wait <seconds> - Wait fixed time
wait_for <selector> - Wait for element
wait_visible <selector> - Wait for visible
wait_hidden <selector> - Wait for hidden
wait_enabled <selector> - Wait for enabled
wait_text <text> - Wait for text
wait_url <pattern> - Wait for URL change
wait_title <title> - Wait for title
wait_load - Wait for page load
wait_network_idle - Wait for network idle
timeout <seconds> - Set default timeout

Data Export & Import

export_html [file] - Export page HTML
export_text [file] - Export page text
export_links [file] - Export all links
export_images [file] - Export image URLs
export_data <selector> [file] - Export table data
import_data <file> - Import test data
save_state [file] - Save browser state
load_state <file> - Load browser state

Automation & Scripting

record - Start recording actions
stop_record - Stop recording
replay <file> - Replay recorded script
macro <name> - Save/run macro
loop <count> <commands> - Loop commands
if <condition> - Conditional execution
else - Else branch
endif - End if block
break - Break from loop
continue - Continue loop
sleep <ms> - Sleep milliseconds
repeat_until <condition> - Repeat until true

Advanced Browser Features

dev_tools - Open developer tools
extensions - List browser extensions
bookmarks - Get bookmarks
downloads - Show download manager
incognito - Switch to incognito mode
clear_cache - Clear browser cache
clear_data - Clear browsing data
import_bookmarks <file> - Import bookmarks
export_bookmarks <file> - Export bookmarks

Accessibility Testing

accessibility_scan - Run accessibility audit
color_contrast <selector> - Check color contrast
alt_text - Check image alt text
heading_structure - Analyze heading structure
keyboard_navigation - Test keyboard nav
screen_reader - Simulate screen reader
focus_order - Check tab order

SEO & Meta Analysis

seo_scan - SEO analysis
meta_tags - Get all meta tags
og_tags - Get Open Graph tags
twitter_cards - Get Twitter card tags
structured_data - Get structured data
canonical_url - Get canonical URL
robots_txt - Get robots.txt
sitemap - Get sitemap

Advanced Network Features

proxy <url> - Set proxy server
vpn <config> - Connect to VPN
dns <server> - Set DNS server
har_export [file] - Export HAR file
network_conditions - Simulate network conditions
websockets - Monitor WebSocket connections
http2_info - Get HTTP/2 info

Browser Automation Utilities

random_user_agent - Set random user agent
random_viewport - Set random viewport
human_typing <text> - Type like human
human_click <selector> - Click like human
mouse_trail - Show mouse movements
captcha_solve - Attempt captcha solving
stealth_mode - Enable stealth mode

System Integration

notify <message> - System notification
sound <file> - Play sound
email <to> <subject> - Send email
slack <channel> <message> - Send Slack message
webhook <url> <data> - Send webhook
