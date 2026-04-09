import os
import sys
import time
import requests
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from jinja2 import Template
from selenium import webdriver
from selenium.common.exceptions import JavascriptException, NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

try:
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    EDGE_DRIVER_AVAILABLE = True
except ImportError:
    EdgeChromiumDriverManager = None
    EDGE_DRIVER_AVAILABLE = False

BASELINE_URL = "https://vehiclehistory.eu/"
DEV_URL = "https://vhreu.accessautohistory.com/"
VIEWPORT_WIDTHS = [360, 375, 380, 390, 400, 420, 430, 450]
BROWSERS = ["chrome", "firefox", "edge"]
REPORT_FILE = "qa_report.html"
SCREENSHOT_DIR = "screenshots"

VIEWPORTS = {
    'desktop': {'width': 1200, 'height': 900},
    'mobile': {'width': 375, 'height': 667}
}

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>QA Comparison Report</title>
  <style>
    body { font-family: Arial, sans-serif; color: #222; margin: 0; padding: 20px; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 24px; }
    th, td { border: 1px solid #ccc; padding: 10px; text-align: left; }
    th { background: #f5f5f5; }
    .passed { color: #1a7f37; font-weight: bold; }
    .failed { color: #c82333; font-weight: bold; }
    .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 24px; }
    .card { padding: 16px; border: 1px solid #ddd; border-radius: 8px; background: #fafafa; }
    .card h3 { margin: 0 0 8px; font-size: 16px; }
    .log-entry { margin-bottom: 8px; white-space: pre-wrap; }
    .section-title { margin-top: 32px; margin-bottom: 12px; font-size: 22px; }
    .small { font-size: 0.92em; color: #555; }
  </style>
</head>
<body>
  <h1>Automated QA Comparison Report</h1>
  <p class="small">Baseline: {{ baseline_url }} | Dev: {{ dev_url }}</p>

  <div class="summary">
    <div class="card"><h3>Headings Passed</h3><div>{{ summary.headings_passed }}</div></div>
    <div class="card"><h3>Headings Failed</h3><div>{{ summary.headings_failed }}</div></div>
    <div class="card"><h3>CTA Checks Passed</h3><div>{{ summary.ctas_passed }}</div></div>
    <div class="card"><h3>CTA Checks Failed</h3><div>{{ summary.ctas_failed }}</div></div>
    <div class="card"><h3>UI/UX Issues Found</h3><div>{{ summary.ui_ux_issues }}</div></div>
  </div>

  <h2 class="section-title">Heading Structure Comparison</h2>
  <table>
    <thead>
      <tr>
        <th>Tag</th>
        <th>Baseline Count</th>
        <th>Dev Count</th>
      </tr>
    </thead>
    <tbody>
      {% for tag, counts in heading_counts.items() %}
      <tr>
        <td>{{ tag }}</td>
        <td>{{ counts.baseline }}</td>
        <td>{{ counts.dev }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <h2 class="section-title">Full Page Screenshots</h2>
  <div style="display:flex; gap:20px; flex-wrap:wrap; margin-bottom:24px;">
    <div style="flex:1 1 45%;">
      <h3>Baseline Page</h3>
      <a href="{{ page_screenshots.baseline }}" target="_blank" title="Open baseline full-page screenshot"><img src="{{ page_screenshots.baseline }}" alt="Baseline screenshot" style="width:100%; border:1px solid #ccc;"/></a>
    </div>
    <div style="flex:1 1 45%;">
      <h3>Dev Page</h3>
      <a href="{{ page_screenshots.dev }}" target="_blank" title="Open dev full-page screenshot"><img src="{{ page_screenshots.dev }}" alt="Dev screenshot" style="width:100%; border:1px solid #ccc;"/></a>
    </div>
  </div>

  <h2 class="section-title">Heading Paragraph Matching</h2>
  <table>
    <thead>
      <tr>
        <th>Tag</th>
        <th>Baseline Heading</th>
        <th>Dev Heading</th>
        <th>Baseline Paragraph</th>
        <th>Dev Paragraph</th>
        <th>Baseline Screenshot</th>
        <th>Dev Screenshot</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      {% for record in heading_comparisons %}
      <tr>
        <td>{{ record.tag }}</td>
        <td>{{ record.baseline_title }}</td>
        <td>{{ record.dev_title }}</td>
        <td>{{ record.baseline_paragraph }}</td>
        <td>{{ record.dev_paragraph }}</td>
        <td>{% if record.screenshot_baseline %}<a href="{{ record.screenshot_baseline }}" target="_blank" title="Open baseline screenshot">SS</a>{% endif %}</td>
        <td>{% if record.screenshot_dev %}<a href="{{ record.screenshot_dev }}" target="_blank" title="Open dev screenshot">SS</a>{% endif %}</td>
        <td class="{{ record.status|lower }}">{{ record.status }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <h2 class="section-title">CTA Scan Results</h2>
  <table>
    <thead>
      <tr>
        <th>Page</th>
        <th>Element</th>
        <th>Destination</th>
        <th>Classification</th>
        <th>Tab Behavior</th>
        <th>HTTP Status</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      {% for cta in cta_results %}
      <tr>
        <td>{{ cta.page }}</td>
        <td>{{ cta.selector }}</td>
        <td>{{ cta.destination }}</td>
        <td>{{ cta.classification }}</td>
        <td>{{ cta.tab_behavior }}</td>
        <td>{{ cta.http_status }}</td>
        <td class="{{ cta.status|lower }}">{{ cta.status }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <h2 class="section-title">Header/Footer Navigation CTA Results</h2>
  <table>
    <thead>
      <tr>
        <th>Section</th>
        <th>Element</th>
        <th>Destination</th>
        <th>Classification</th>
        <th>Tab Behavior</th>
      </tr>
    </thead>
    <tbody>
      {% for cta in header_footer_ctas %}
      <tr>
        <td>{{ cta.section }}</td>
        <td>{{ cta.selector }}</td>
        <td>{{ cta.destination }}</td>
        <td>{{ cta.classification }}</td>
        <td>{{ cta.tab_behavior }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <h2 class="section-title">UI/UX Test Issues Summary</h2>
  <table>
    <thead>
      <tr>
        <th>Viewport</th>
        <th>URL</th>
        <th>Step</th>
        <th>Scroll Position</th>
        <th>Issue Type</th>
        <th>Element</th>
        <th>Details</th>
      </tr>
    </thead>
    <tbody>
      {% if ui_ux_issues and ui_ux_issues|length > 0 %}
        {% for issue in ui_ux_issues %}
        <tr style="background: rgba(255, 0, 0, 0.05);">
          <td>{{ issue.viewport }}</td>
          <td>{{ issue.url }}</td>
          <td>{{ issue.step }}</td>
          <td>{{ issue.scroll_position }}px</td>
          <td class="failed">{{ issue.type }}</td>
          <td>{{ issue.element }}</td>
          <td>{{ issue.text }}</td>
        </tr>
        {% endfor %}
      {% else %}
        <tr>
          <td colspan="7" style="text-align:center; color:#666;">No UI/UX issues detected</td>
        </tr>
      {% endif %}
    </tbody>
  </table>

  <h2 class="section-title">UI/UX Test Screenshots</h2>
  <div style="display:flex; flex-wrap:wrap; gap:10px;">
    {% for ss in ui_ux_screenshots %}
    <div style="flex:1 1 200px;">
      <a href="{{ ss }}" target="_blank" title="Open UI/UX screenshot"><img src="{{ ss }}" alt="UI/UX screenshot" style="width:100%; border:1px solid #ccc;"/></a>
    </div>
    {% endfor %}
  </div>

  <h2 class="section-title">Detailed Log</h2>
  {% for entry in log_entries %}
  <div class="log-entry">{{ entry }}</div>
  {% endfor %}
</body>
</html>
"""


def normalize_text(text):
    if text is None:
        return ""
    return " ".join(text.strip().split())


def find_nearest_text_block(element):
    paragraph = element.find_next("p")
    if paragraph and normalize_text(paragraph.get_text()):
        return paragraph

    for sibling in element.next_siblings:
        if getattr(sibling, "name", None) in ["p", "div", "section", "article"]:
            if normalize_text(sibling.get_text()):
                nested_p = sibling.find("p")
                return nested_p if nested_p else sibling

    next_container = element.find_next(lambda tag: tag.name in ["div", "section", "article"] and normalize_text(tag.get_text()))
    if next_container:
        nested_p = next_container.find("p")
        return nested_p if nested_p else next_container
    return None


def is_internal_link(url, page_url):
    if not url:
        return False
    parsed_page = urlparse(page_url)
    parsed_link = urlparse(urljoin(page_url, url))
    return parsed_page.netloc == parsed_link.netloc


def build_driver():
    # Try minimal driver without Options to avoid pageLoadStrategy issues
    try:
        driver = webdriver.Chrome(service=webdriver.chrome.service.Service(ChromeDriverManager().install()))
        driver.set_page_load_timeout(60)
        return driver
    except Exception as e:
        print(f"[driver] Failed to create driver: {e}")
        raise


def wait_for_document(driver, timeout=20):
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except TimeoutException:
        pass


def extract_headings(driver):
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, "html.parser")
    headings = []
    for level in range(1, 7):
        for element in soup.find_all(f"h{level}"):
            title = normalize_text(element.get_text())
            paragraph = ""
            nearest = find_nearest_text_block(element)
            if nearest:
                paragraph = normalize_text(nearest.get_text())
            headings.append({
                "tag": f"h{level}",
                "title": title,
                "paragraph": paragraph,
            })
    return headings


def get_http_status(url):
    try:
        if url.startswith('http'):
            response = requests.head(url, timeout=2, allow_redirects=True)  # Reduced timeout from 5 to 2 seconds
            return response.status_code
        return None
    except requests.Timeout:
        return "Timeout"
    except Exception:
        return "N/A"


def classify_cta_element(driver, element, page_url, page_label, skip_http_check=False):
    try:
        selector = element.get_attribute("outerHTML") or ""
        href = element.get_attribute("href") or ""
        target = element.get_attribute("target") or ""
        onclick = element.get_attribute("onclick") or ""
        destination = href or onclick or element.get_attribute("formaction") or "[no href]"
        
        # Skip HTTP check for javascript: and mailto: links, or if skip_http_check is True
        if skip_http_check or destination.startswith(('javascript:', 'mailto:', '#', 'tel:')) or not destination.startswith('http'):
            http_status = "N/A"
            status = "Passed"
        else:
            # Only check HTTP status for absolute URLs
            http_status = get_http_status(destination) if href and href.startswith('http') else "N/A"
            status = "Passed" if http_status == 200 else "Failed" if http_status not in ["N/A", "Timeout"] else "N/A"
        
        internal = is_internal_link(href, page_url) if href else False
        
        if href:
            if target == "_blank" or not internal:
                classification = "External"
                tab_behavior = "External tab" if target == "_blank" else "External same tab"
            else:
                classification = "Internal"
                tab_behavior = "Internal tab"
        else:
            if "window.open" in onclick or "_blank" in onclick:
                classification = "External"
                tab_behavior = "External tab"
            else:
                classification = "Internal"
                tab_behavior = "Internal tab"
        
        return {
            "page": page_label,
            "selector": selector[:300],
            "destination": destination[:200],
            "classification": classification,
            "tab_behavior": tab_behavior,
            "notes": "button or clickable CTA" if element.tag_name.lower() in ["button", "input"] else "link CTA",
            "http_status": http_status,
            "status": status,
        }
    except Exception as e:
        print(f"[cta] Error classifying element: {e}")
        return None


def scan_ctas(driver, page_label):
    results = []
    try:
        elements = driver.find_elements(By.TAG_NAME, "a") + driver.find_elements(By.TAG_NAME, "button")
        print(f"[cta] Found {len(elements)} CTA elements on {page_label}")
        
        elements = elements[:50]  # Limit to first 50 to prevent timeout
        for idx, element in enumerate(elements, 1):
            try:
                info = classify_cta_element(driver, element, driver.current_url, page_label)
                if info:
                    results.append(info)
                if idx % 10 == 0:
                    print(f"[cta] Scanned {idx} CTAs on {page_label}...")
            except Exception:
                continue
        
        print(f"[cta] Completed CTA scan for {page_label}: {len(results)} CTAs processed")
    except Exception as e:
        print(f"[cta] Error scanning CTAs: {e}")
    
    return results


def scan_header_footer_ctas(driver, page_label):
    results = []
    try:
        for section, selector in [("Header", "header"), ("Footer", "footer")]:
            try:
                container = driver.find_element(By.CSS_SELECTOR, selector)
            except NoSuchElementException:
                continue
            
            elements = container.find_elements(By.TAG_NAME, "a") + container.find_elements(By.TAG_NAME, "button")
            print(f"[cta] Found {len(elements)} CTAs in {section}")
            
            for element in elements[:20]:  # Limit to first 20 per section
                try:
                    # Skip HTTP checking for header/footer elements to prevent hanging
                    info = classify_cta_element(driver, element, driver.current_url, page_label, skip_http_check=True)
                    if info:
                        info["section"] = section
                        results.append(info)
                except Exception:
                    continue
    except Exception as e:
        print(f"[cta] Error scanning header/footer CTAs: {e}")
    
    return results


def compare_headings(baseline_headings, dev_headings):
    counts = {f"h{i}": {"baseline": 0, "dev": 0} for i in range(1, 7)}
    for heading in baseline_headings:
        counts[heading["tag"]]["baseline"] += 1
    for heading in dev_headings:
        counts[heading["tag"]]["dev"] += 1

    baseline_map = {}
    for heading in baseline_headings:
        key = (heading["tag"], heading["title"])
        baseline_map[key] = heading["paragraph"]

    dev_map = {}
    for heading in dev_headings:
        key = (heading["tag"], heading["title"])
        dev_map[key] = heading["paragraph"]

    comparisons = []
    all_keys = set(baseline_map.keys()) | set(dev_map.keys())
    passed = 0
    failed = 0

    for key in sorted(all_keys):
        tag, title = key
        baseline_para = baseline_map.get(key, "[missing]")
        dev_para = dev_map.get(key, "[missing]")
        status = "Passed" if baseline_para == dev_para else "Failed"
        if status == "Passed":
            passed += 1
        else:
            failed += 1
        comparisons.append({
            "tag": tag,
            "baseline_title": title if key in baseline_map else "[missing]",
            "dev_title": title if key in dev_map else "[missing]",
            "baseline_paragraph": baseline_para,
            "dev_paragraph": dev_para,
            "status": status,
            "screenshot_baseline": "",
            "screenshot_dev": "",
        })

    return counts, comparisons, passed, failed


def capture_full_page_screenshot(driver, filename):
    try:
        screenshot_path = os.path.join(SCREENSHOT_DIR, filename)
        driver.save_screenshot(screenshot_path)
        return screenshot_path
    except Exception as e:
        print(f"[screenshot] Error capturing {filename}: {e}")
        return ""


def highlight_heading_and_paragraph(driver, tag, title):
    script = f"""
    var headings = document.querySelectorAll('{tag}');
    for (var i = 0; i < headings.length; i++) {{
        var heading = headings[i];
        if (heading.textContent.trim() === '{title.replace("'", "\\'")}') {{
            heading.style.outline = '3px solid red';
            heading.style.backgroundColor = 'rgba(255, 0, 0, 0.1)';
            
            // Find next paragraph
            var nextElement = heading.nextElementSibling;
            while (nextElement) {{
                if (nextElement.tagName === 'P' || nextElement.tagName === 'DIV' || nextElement.tagName === 'SECTION') {{
                    nextElement.style.outline = '3px solid blue';
                    nextElement.style.backgroundColor = 'rgba(0, 0, 255, 0.1)';
                    break;
                }}
                nextElement = nextElement.nextElementSibling;
            }}
            break;
        }}
    }}
    """
    try:
        driver.execute_script(script)
    except JavascriptException:
        pass


def detect_ui_issues(driver):
    script = """
    var issues = [];
    var elements = document.querySelectorAll('*');
    for (var i = 0; i < elements.length; i++) {
        var el = elements[i];
        var rect = el.getBoundingClientRect();
        var computedStyle = window.getComputedStyle(el);
        var overflow = computedStyle.overflow;
        var overflowX = computedStyle.overflowX;
        var overflowY = computedStyle.overflowY;
        
        if (overflowX === 'hidden' && rect.width > window.innerWidth) {
            issues.push({type: 'overflow-x', element: el.tagName, text: el.textContent.substring(0, 50)});
            el.style.outline = '3px solid red';
            el.style.backgroundColor = 'rgba(255, 0, 0, 0.1)';
        }
        
        if ((overflow === 'hidden' || overflow === 'auto') && (rect.right > window.innerWidth || rect.bottom > window.innerHeight)) {
            issues.push({type: 'hidden-overflow', element: el.tagName});
            el.style.outline = '3px solid red';
        }
    }
    return issues;
    """
    try:
        return driver.execute_script(script)
    except JavascriptException:
        return []


def perform_ui_ux_test(driver, page_url, viewport_name, screenshot_dir):
    print(f"[ui/ux] Starting UI/UX test for {page_url} on {viewport_name}")
    driver.get(page_url)
    wait_for_document(driver)
    time.sleep(2)
    
    # Get page dimensions
    scroll_height = driver.execute_script("return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
    viewport_height = driver.execute_script("return window.innerHeight")
    step_size = 300  # Scroll in increments
    
    screenshots = []
    all_issues = []
    current_scroll = 0
    scroll_count = 0
    
    print(f"[ui/ux] Page scroll height: {scroll_height}px, viewport: {viewport_height}px")
    
    # Scroll from top to bottom
    while current_scroll <= scroll_height:
        scroll_count += 1
        print(f"[ui/ux] Scrolling to position {current_scroll}px (step {scroll_count})")
        
        # Scroll to position
        driver.execute_script(f"window.scrollTo(0, {current_scroll});")
        time.sleep(1.5)  # Wait for lazy loading and rendering
        
        # Detect issues at this scroll position
        issues = detect_ui_issues(driver)
        if issues and len(issues) > 0:
            print(f"[ui/ux] Found {len(issues)} UI issues at scroll {current_scroll}px")
            for issue in issues:
                all_issues.append({
                    "scroll_position": current_scroll,
                    "type": issue.get("type", "unknown"),
                    "element": issue.get("element", "unknown"),
                    "text": issue.get("text", "")[:100],
                    "step": scroll_count,
                    "viewport": viewport_name,
                    "url": page_url
                })
        
        # Capture screenshot with highlighted issues
        screenshot_path = os.path.join(screenshot_dir, f"ui_ux_{viewport_name}_step_{scroll_count:03d}_scroll_{current_scroll}.png")
        driver.save_screenshot(screenshot_path)
        screenshots.append(screenshot_path)
        print(f"[ui/ux] Screenshot saved: {screenshot_path}")
        
        # Move to next position
        current_scroll += step_size
        time.sleep(0.5)
    
    # Final screenshot at bottom
    driver.execute_script(f"window.scrollTo(0, {scroll_height});")
    time.sleep(1)
    final_screenshot = os.path.join(screenshot_dir, f"ui_ux_{viewport_name}_final_bottom.png")
    driver.save_screenshot(final_screenshot)
    screenshots.append(final_screenshot)
    
    print(f"[ui/ux] UI/UX test completed: {len(screenshots)} screenshots, {len(all_issues)} issues detected")
    return screenshots, len(all_issues), all_issues


def generate_report(data, filename):
    template = Template(HTML_TEMPLATE)
    html = template.render(**data)
    with open(filename, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"Report generated: {filename}")


def main():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    log_entries = []
    
    print("[init] Starting QA comparison test suite in split mode")
    
    # Create two drivers for split view
    baseline_driver = build_driver()
    dev_driver = build_driver()
    
    # Set up split view: baseline on left, dev on right
    baseline_driver.set_window_position(0, 0)
    baseline_driver.set_window_size(VIEWPORTS['desktop']['width'], VIEWPORTS['desktop']['height'])
    dev_driver.set_window_position(VIEWPORTS['desktop']['width'], 0)
    dev_driver.set_window_size(VIEWPORTS['desktop']['width'], VIEWPORTS['desktop']['height'])
    
    ui_ux_screenshots = []
    ui_ux_issues_details = []
    ui_ux_issue_count = 0
    
    try:
        # Step 1: Extract headings from both pages in split view
        print("[step 1] Heading Structure Comparison - Split View Mode")
        baseline_driver.get(BASELINE_URL)
        wait_for_document(baseline_driver)
        baseline_headings = extract_headings(baseline_driver)
        print(f"[baseline] Found {len(baseline_headings)} headings")
        
        dev_driver.get(DEV_URL)
        wait_for_document(dev_driver)
        dev_headings = extract_headings(dev_driver)
        print(f"[dev] Found {len(dev_headings)} headings")
        
        # Compare headings
        heading_counts, heading_comparisons, headings_passed, headings_failed = compare_headings(
            baseline_headings, dev_headings
        )
        log_entries.append(f"Heading comparison: {headings_passed} passed, {headings_failed} failed")
        
        # Step 2: Capture full-page screenshots
        print("[step 2] Capturing Full-Page Screenshots")
        baseline_driver.get(BASELINE_URL)
        wait_for_document(baseline_driver)
        time.sleep(1)
        page_baseline = capture_full_page_screenshot(baseline_driver, "baseline_full.png")
        
        dev_driver.get(DEV_URL)
        wait_for_document(dev_driver)
        time.sleep(1)
        page_dev = capture_full_page_screenshot(dev_driver, "dev_full.png")
        
        page_screenshots = {"baseline": page_baseline, "dev": page_dev}
        
        # Step 3: Scan CTAs from both pages
        print("[step 3] Scanning CTA Elements")
        dev_driver.get(DEV_URL)
        wait_for_document(dev_driver)
        cta_results = []
        cta_results.extend(scan_ctas(dev_driver, "Dev"))
        
        baseline_driver.get(BASELINE_URL)
        wait_for_document(baseline_driver)
        cta_results.extend(scan_ctas(baseline_driver, "Baseline"))
        
        log_entries.append(f"CTA scan: {len(cta_results)} elements found")
        
        # Step 4: Header/Footer CTAs
        print("[step 4] Scanning Header/Footer Navigation")
        dev_driver.get(DEV_URL)
        wait_for_document(dev_driver)
        header_footer_ctas = []
        header_footer_ctas.extend(scan_header_footer_ctas(dev_driver, "Dev"))
        
        baseline_driver.get(BASELINE_URL)
        wait_for_document(baseline_driver)
        header_footer_ctas.extend(scan_header_footer_ctas(baseline_driver, "Baseline"))
        
        # Step 5: UI/UX Test - Both URLs and Both Viewports (Desktop & Mobile)
        print("[step 5] UI/UX Test - Both URLs, Desktop & Mobile Viewports")
        
        for viewport_name, viewport in VIEWPORTS.items():
            print(f"[ui/ux] Testing {viewport_name} viewport ({viewport['width']}x{viewport['height']})")
            
            # Set viewport sizes for both drivers
            baseline_driver.set_window_size(viewport['width'], viewport['height'])
            dev_driver.set_window_size(viewport['width'], viewport['height'])
            
            # Run UI/UX test on baseline
            baseline_screenshots, baseline_issues_count, baseline_issues = perform_ui_ux_test(
                baseline_driver, BASELINE_URL, f"baseline_{viewport_name}", SCREENSHOT_DIR
            )
            ui_ux_screenshots.extend(baseline_screenshots)
            ui_ux_issues_details.extend(baseline_issues)
            ui_ux_issue_count += baseline_issues_count
            
            # Run UI/UX test on dev
            dev_screenshots, dev_issues_count, dev_issues = perform_ui_ux_test(
                dev_driver, DEV_URL, f"dev_{viewport_name}", SCREENSHOT_DIR
            )
            ui_ux_screenshots.extend(dev_screenshots)
            ui_ux_issues_details.extend(dev_issues)
            ui_ux_issue_count += dev_issues_count
            
            log_entries.append(f"UI/UX {viewport_name}: baseline {baseline_issues_count} issues, dev {dev_issues_count} issues")
        
        # Heading paragraph matching screenshots
        print("[step 6] Heading Paragraph Matching Screenshots")
        for idx, record in enumerate(heading_comparisons, start=1):
            if record["baseline_title"] != "[missing]":
                baseline_driver.get(BASELINE_URL)
                wait_for_document(baseline_driver)
                highlight_heading_and_paragraph(baseline_driver, record["tag"], record["baseline_title"])
                record["screenshot_baseline"] = capture_full_page_screenshot(baseline_driver, f"heading_{idx}_baseline.png")
            else:
                record["screenshot_baseline"] = ""
            
            if record["dev_title"] != "[missing]":
                dev_driver.get(DEV_URL)
                wait_for_document(dev_driver)
                highlight_heading_and_paragraph(dev_driver, record["tag"], record["dev_title"])
                record["screenshot_dev"] = capture_full_page_screenshot(dev_driver, f"heading_{idx}_dev.png")
            else:
                record["screenshot_dev"] = ""
        
    finally:
        baseline_driver.quit()
        dev_driver.quit()
    
    # Summary stats
    ctas_passed = sum(1 for c in cta_results if c.get("status") == "Passed")
    ctas_failed = sum(1 for c in cta_results if c.get("status") == "Failed")
    
    report_data = {
        "baseline_url": BASELINE_URL,
        "dev_url": DEV_URL,
        "heading_counts": heading_counts,
        "heading_comparisons": heading_comparisons,
        "cta_results": cta_results,
        "header_footer_ctas": header_footer_ctas,
        "ui_ux_screenshots": ui_ux_screenshots,
        "ui_ux_issues": ui_ux_issues_details,
        "ui_ux_issue_count": ui_ux_issue_count,
        "log_entries": log_entries,
        "page_screenshots": page_screenshots,
        "summary": {
            "headings_passed": headings_passed,
            "headings_failed": headings_failed,
            "ctas_passed": ctas_passed,
            "ctas_failed": ctas_failed,
            "ui_ux_issues": ui_ux_issue_count,
        },
    }
    generate_report(report_data, REPORT_FILE)
    print(f"\n[complete] Report generated: {REPORT_FILE}")


if __name__ == "__main__":
    main()


def normalize_text(text):
    if text is None:
        return ""
    return " ".join(text.strip().split())


def find_nearest_text_block(element):
    paragraph = element.find_next("p")
    if paragraph and normalize_text(paragraph.get_text()):
        return paragraph

    for sibling in element.next_siblings:
        if getattr(sibling, "name", None) in ["p", "div", "section", "article"]:
            if normalize_text(sibling.get_text()):
                nested_p = sibling.find("p")
                return nested_p if nested_p else sibling

    next_container = element.find_next(lambda tag: tag.name in ["div", "section", "article"] and normalize_text(tag.get_text()))
    if next_container:
        nested_p = next_container.find("p")
        return nested_p if nested_p else next_container
    return None


def is_internal_link(url, page_url):
    if not url:
        return False
    parsed_page = urlparse(page_url)
    parsed_link = urlparse(urljoin(page_url, url))
    return parsed_page.netloc == parsed_link.netloc


def build_driver():
    # Try minimal driver without Options to avoid pageLoadStrategy issues
    try:
        driver = webdriver.Chrome(service=webdriver.chrome.service.Service(ChromeDriverManager().install()))
        driver.set_page_load_timeout(60)
        return driver
    except Exception as e:
        print(f"[driver] Failed to create driver: {e}")
        raise


def wait_for_document(driver, timeout=20):
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except TimeoutException:
        pass


def extract_headings(driver):
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, "html.parser")
    headings = []
    for level in range(1, 7):
        for element in soup.find_all(f"h{level}"):
            title = normalize_text(element.get_text())
            paragraph = ""
            nearest = find_nearest_text_block(element)
            if nearest:
                paragraph = normalize_text(nearest.get_text())
            headings.append({
                "tag": f"h{level}",
                "title": title,
                "paragraph": paragraph,
            })
    return headings


def get_http_status(url):
    try:
        if url.startswith('http'):
            response = requests.head(url, timeout=2, allow_redirects=True)  # Reduced timeout from 5 to 2 seconds
            return response.status_code
        return None
    except requests.Timeout:
        return "Timeout"
    except Exception:
        return "N/A"


def classify_cta_element(driver, element, page_url, page_label, skip_http_check=False):
    try:
        selector = element.get_attribute("outerHTML") or ""
        href = element.get_attribute("href") or ""
        target = element.get_attribute("target") or ""
        onclick = element.get_attribute("onclick") or ""
        destination = href or onclick or element.get_attribute("formaction") or "[no href]"
        
        # Skip HTTP check for javascript: and mailto: links, or if skip_http_check is True
        if skip_http_check or destination.startswith(('javascript:', 'mailto:', '#', 'tel:')) or not destination.startswith('http'):
            http_status = "N/A"
            status = "Passed"
        else:
            # Only check HTTP status for absolute URLs
            http_status = get_http_status(destination) if href and href.startswith('http') else "N/A"
            status = "Passed" if http_status == 200 else "Failed" if http_status not in ["N/A", "Timeout"] else "N/A"
        
        internal = is_internal_link(href, page_url) if href else False
        
        if href:
            if target == "_blank" or not internal:
                classification = "External"
                tab_behavior = "External tab" if target == "_blank" else "External same tab"
            else:
                classification = "Internal"
                tab_behavior = "Internal tab"
        else:
            if "window.open" in onclick or "_blank" in onclick:
                classification = "External"
                tab_behavior = "External tab"
            else:
                classification = "Internal"
                tab_behavior = "Internal tab"
        
        return {
            "page": page_label,
            "selector": selector[:300],
            "destination": destination[:200],
            "classification": classification,
            "tab_behavior": tab_behavior,
            "notes": "button or clickable CTA" if element.tag_name.lower() in ["button", "input"] else "link CTA",
            "http_status": http_status,
            "status": status,
        }
    except Exception as e:
        return {
            "page": page_label,
            "selector": "Unable to parse",
            "destination": "Error",
            "classification": "Unknown",
            "tab_behavior": "Unknown",
            "notes": f"Error: {str(e)[:50]}",
            "http_status": "Error",
            "status": "Failed",
        }



def scan_ctas(driver, page_label):
    results = []
    try:
        elements = []
        elements.extend(driver.find_elements(By.TAG_NAME, "a"))
        elements.extend(driver.find_elements(By.TAG_NAME, "button"))
        elements.extend(driver.find_elements(By.CSS_SELECTOR, "input[type=button], input[type=submit]"))
        page_url = driver.current_url
        
        print(f"[cta] Found {len(elements)} CTA elements on {page_label}")
        
        # Limit to first 50 CTAs to avoid timeout
        elements = elements[:50]
        
        for idx, element in enumerate(elements, 1):
            try:
                info = classify_cta_element(driver, element, page_url, page_label)
                results.append(info)
                if idx % 10 == 0:
                    print(f"[cta] Scanned {idx} CTAs on {page_label}...")
            except Exception:
                continue
        
        print(f"[cta] Completed CTA scan for {page_label}: {len(results)} CTAs processed")
    except Exception as e:
        print(f"[cta] Error scanning CTAs: {e}")
    
    return results


def scan_header_footer_ctas(driver, page_label):
    results = []
    try:
        for section, selector in [("Header", "header"), ("Footer", "footer")]:
            try:
                container = driver.find_element(By.CSS_SELECTOR, selector)
            except NoSuchElementException:
                continue
            
            elements = container.find_elements(By.TAG_NAME, "a") + container.find_elements(By.TAG_NAME, "button")
            print(f"[cta] Found {len(elements)} CTAs in {section}")
            
            for element in elements[:20]:  # Limit to first 20 per section
                try:
                    # Skip HTTP checking for header/footer elements to prevent hanging
                    info = classify_cta_element(driver, element, driver.current_url, page_label, skip_http_check=True)
                    info["section"] = section
                    results.append(info)
                except Exception:
                    continue
    except Exception as e:
        print(f"[cta] Error scanning header/footer CTAs: {e}")
    
    return results


def compare_headings(baseline_headings, dev_headings):
    counts = {f"h{i}": {"baseline": 0, "dev": 0} for i in range(1, 7)}
    for heading in baseline_headings:
        counts[heading["tag"]]["baseline"] += 1
    for heading in dev_headings:
        counts[heading["tag"]]["dev"] += 1

    baseline_map = {}
    for heading in baseline_headings:
        key = (heading["tag"], heading["title"])
        baseline_map[key] = heading["paragraph"]

    dev_map = {}
    for heading in dev_headings:
        key = (heading["tag"], heading["title"])
        dev_map[key] = heading["paragraph"]

    comparisons = []
    passed = 0
    failed = 0

    for key, baseline_para in baseline_map.items():
        tag, title = key
        dev_para = dev_map.get(key, "[missing dev heading]")
        status = "Passed" if baseline_para and dev_para and normalize_text(baseline_para) == normalize_text(dev_para) else "Failed"
        if dev_para == "[missing dev heading]":
            status = "Failed"
        if status == "Passed":
            passed += 1
        else:
            failed += 1
        comparisons.append({
            "tag": tag,
            "baseline_title": title,
            "dev_title": title if key in dev_map else "[missing]",
            "baseline_paragraph": baseline_para or "[none]",
            "dev_paragraph": dev_para if dev_para else "[none]",
            "status": status,
        })

    for key, dev_para in dev_map.items():
        if key not in baseline_map:
            tag, title = key
            comparisons.append({
                "tag": tag,
                "baseline_title": "[missing]",
                "dev_title": title,
                "baseline_paragraph": "[missing]",
                "dev_paragraph": dev_para or "[none]",
                "status": "Failed",
            })
            failed += 1

    return counts, comparisons, passed, failed


def capture_full_page_screenshot(driver, filename):
    height = driver.execute_script(
        "return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, document.body.offsetHeight, document.documentElement.offsetHeight)"
    )
    width = driver.execute_script(
        "return Math.max(document.body.scrollWidth, document.documentElement.scrollWidth, document.body.offsetWidth, document.documentElement.offsetWidth)"
    )
    width = min(width, 1800)
    height = min(height, 12000)
    try:
        driver.set_window_size(width, height)
    except Exception:
        pass
    filepath = os.path.join(SCREENSHOT_DIR, filename)
    driver.save_screenshot(filepath)
    return filepath


def highlight_heading_and_paragraph(driver, tag, title):
    script = r"""
    const tag = arguments[0];
    const text = arguments[1];
    const normalize = s => s.replace(/\s+/g, ' ').trim();
    const candidates = Array.from(document.getElementsByTagName(tag));
    const heading = candidates.find(el => normalize(el.textContent).includes(normalize(text)));
    if (heading) {
        heading.style.outline = '4px solid red';
        heading.style.backgroundColor = 'rgba(255, 220, 220, 0.7)';
        let next = heading.nextElementSibling;
        while (next) {
            if (next.tagName.toLowerCase() === 'p' && normalize(next.textContent)) {
                next.style.outline = '3px dashed red';
                next.style.backgroundColor = 'rgba(255, 240, 240, 0.7)';
                return true;
            }
            if (['div','section','article'].includes(next.tagName.toLowerCase()) && normalize(next.textContent)) {
                next.style.outline = '3px dashed red';
                next.style.backgroundColor = 'rgba(255, 240, 240, 0.7)';
                return true;
            }
            next = next.nextElementSibling;
        }
        const found = heading.querySelector('p');
        if (found && normalize(found.textContent)) {
            found.style.outline = '3px dashed red';
            found.style.backgroundColor = 'rgba(255, 240, 240, 0.7)';
            return true;
        }
        return true;
    }
    return false;
    """
    return driver.execute_script(script, tag, title)


def detect_ui_issues(driver):
    script = r"""
    const issues = [];
    const elements = document.querySelectorAll('*');
    for (let el of elements) {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        const overflow = style.overflow || 'visible';
        
        if (rect.width > window.innerWidth + 10) {
            issues.push({type: 'overflow-x', element: el.tagName, text: el.textContent.substring(0, 50)});
            el.style.outline = '3px solid red';
            el.style.backgroundColor = 'rgba(255, 0, 0, 0.1)';
        }
        if (rect.height > window.innerHeight + 100 && rect.height < window.innerHeight + 200) {
            issues.push({type: 'misaligned-height', element: el.tagName});
            el.style.outline = '2px solid orange';
        }
        if ((overflow === 'hidden' || overflow === 'auto') && (rect.right > window.innerWidth || rect.bottom > window.innerHeight)) {
            issues.push({type: 'hidden-overflow', element: el.tagName});
            el.style.outline = '3px solid red';
        }
    }
    return issues;
    """
    return driver.execute_script(script)


def perform_ui_ux_test(driver, page_url, viewport_name, screenshot_dir):
    print(f"[ui/ux] Starting UI/UX test for {page_url} on {viewport_name}")
    driver.get(page_url)
    wait_for_document(driver)
    time.sleep(2)
    
    # Get page dimensions
    scroll_height = driver.execute_script("return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
    viewport_height = driver.execute_script("return window.innerHeight")
    step_size = 300  # Scroll in increments
    
    screenshots = []
    all_issues = []
    current_scroll = 0
    scroll_count = 0
    
    print(f"[ui/ux] Page scroll height: {scroll_height}px, viewport: {viewport_height}px")
    
    # Scroll from top to bottom
    while current_scroll <= scroll_height:
        scroll_count += 1
        print(f"[ui/ux] Scrolling to position {current_scroll}px (step {scroll_count})")
        
        # Scroll to position
        driver.execute_script(f"window.scrollTo(0, {current_scroll});")
        time.sleep(1.5)  # Wait for lazy loading and rendering
        
        # Detect issues at this scroll position
        issues = detect_ui_issues(driver)
        if issues and len(issues) > 0:
            print(f"[ui/ux] Found {len(issues)} UI issues at scroll {current_scroll}px")
            for issue in issues:
                all_issues.append({
                    "scroll_position": current_scroll,
                    "type": issue.get("type", "unknown"),
                    "element": issue.get("element", "unknown"),
                    "text": issue.get("text", "")[:100],
                    "step": scroll_count,
                    "viewport": viewport_name,
                    "url": page_url
                })
        
        # Capture screenshot with highlighted issues
        screenshot_path = os.path.join(screenshot_dir, f"ui_ux_{viewport_name}_step_{scroll_count:03d}_scroll_{current_scroll}.png")
        driver.save_screenshot(screenshot_path)
        screenshots.append(screenshot_path)
        print(f"[ui/ux] Screenshot saved: {screenshot_path}")
        
        # Move to next position
        current_scroll += step_size
        time.sleep(0.5)
    
    # Final screenshot at bottom
    driver.execute_script(f"window.scrollTo(0, {scroll_height});")
    time.sleep(1)
    final_screenshot = os.path.join(screenshot_dir, f"ui_ux_{viewport_name}_final_bottom.png")
    driver.save_screenshot(final_screenshot)
    screenshots.append(final_screenshot)
    
    print(f"[ui/ux] UI/UX test completed: {len(screenshots)} screenshots, {len(all_issues)} issues detected")
    return screenshots, len(all_issues), all_issues


def generate_report(data, filename):
    template = Template(HTML_TEMPLATE)
    html = template.render(**data)
    with open(filename, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"Report generated: {filename}")


def main():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    log_entries = []
    
    print("[init] Starting QA comparison test suite in split mode")
    
    # Create two drivers for split view
    baseline_driver = build_driver()
    dev_driver = build_driver()
    
    # Set up split view: baseline on left, dev on right
    baseline_driver.set_window_position(0, 0)
    baseline_driver.set_window_size(VIEWPORTS['desktop']['width'], VIEWPORTS['desktop']['height'])
    dev_driver.set_window_position(VIEWPORTS['desktop']['width'], 0)
    dev_driver.set_window_size(VIEWPORTS['desktop']['width'], VIEWPORTS['desktop']['height'])
    
    ui_ux_screenshots = []
    ui_ux_issues_details = []
    ui_ux_issue_count = 0
    
    try:
        # Step 1: Extract headings from both pages in split view
        print("[step 1] Heading Structure Comparison - Split View Mode")
        baseline_driver.get(BASELINE_URL)
        wait_for_document(baseline_driver)
        baseline_headings = extract_headings(baseline_driver)
        print(f"[baseline] Found {len(baseline_headings)} headings")
        
        dev_driver.get(DEV_URL)
        wait_for_document(dev_driver)
        dev_headings = extract_headings(dev_driver)
        print(f"[dev] Found {len(dev_headings)} headings")
        
        # Compare headings
        heading_counts, heading_comparisons, headings_passed, headings_failed = compare_headings(
            baseline_headings, dev_headings
        )
        log_entries.append(f"Heading comparison: {headings_passed} passed, {headings_failed} failed")
        
        # Step 2: Capture full-page screenshots
        print("[step 2] Capturing Full-Page Screenshots")
        baseline_driver.get(BASELINE_URL)
        wait_for_document(baseline_driver)
        time.sleep(1)
        page_baseline = capture_full_page_screenshot(baseline_driver, "baseline_full.png")
        
        dev_driver.get(DEV_URL)
        wait_for_document(dev_driver)
        time.sleep(1)
        page_dev = capture_full_page_screenshot(dev_driver, "dev_full.png")
        
        page_screenshots = {"baseline": page_baseline, "dev": page_dev}
        
        # Step 3: Scan CTAs from both pages
        print("[step 3] Scanning CTA Elements")
        dev_driver.get(DEV_URL)
        wait_for_document(dev_driver)
        cta_results = []
        cta_results.extend(scan_ctas(dev_driver, "Dev"))
        
        baseline_driver.get(BASELINE_URL)
        wait_for_document(baseline_driver)
        cta_results.extend(scan_ctas(baseline_driver, "Baseline"))
        
        log_entries.append(f"CTA scan: {len(cta_results)} elements found")
        
        # Step 4: Header/Footer CTAs
        print("[step 4] Scanning Header/Footer Navigation")
        dev_driver.get(DEV_URL)
        wait_for_document(dev_driver)
        header_footer_ctas = []
        header_footer_ctas.extend(scan_header_footer_ctas(dev_driver, "Dev"))
        
        baseline_driver.get(BASELINE_URL)
        wait_for_document(baseline_driver)
        header_footer_ctas.extend(scan_header_footer_ctas(baseline_driver, "Baseline"))
        
        # Step 5: UI/UX Test - Both URLs and Both Viewports (Desktop & Mobile)
        print("[step 5] UI/UX Test - Both URLs, Desktop & Mobile Viewports")
        
        for viewport_name, viewport in VIEWPORTS.items():
            print(f"[ui/ux] Testing {viewport_name} viewport ({viewport['width']}x{viewport['height']})")
            
            # Set viewport sizes for both drivers
            baseline_driver.set_window_size(viewport['width'], viewport['height'])
            dev_driver.set_window_size(viewport['width'], viewport['height'])
            
            # Run UI/UX test on baseline
            baseline_screenshots, baseline_issues_count, baseline_issues = perform_ui_ux_test(
                baseline_driver, BASELINE_URL, f"baseline_{viewport_name}", SCREENSHOT_DIR
            )
            ui_ux_screenshots.extend(baseline_screenshots)
            ui_ux_issues_details.extend(baseline_issues)
            ui_ux_issue_count += baseline_issues_count
            
            # Run UI/UX test on dev
            dev_screenshots, dev_issues_count, dev_issues = perform_ui_ux_test(
                dev_driver, DEV_URL, f"dev_{viewport_name}", SCREENSHOT_DIR
            )
            ui_ux_screenshots.extend(dev_screenshots)
            ui_ux_issues_details.extend(dev_issues)
            ui_ux_issue_count += dev_issues_count
            
            log_entries.append(f"UI/UX {viewport_name}: baseline {baseline_issues_count} issues, dev {dev_issues_count} issues")
        
        # Heading paragraph matching screenshots
        print("[step 6] Heading Paragraph Matching Screenshots")
        for idx, record in enumerate(heading_comparisons, start=1):
            if record["baseline_title"] != "[missing]":
                baseline_driver.get(BASELINE_URL)
                wait_for_document(baseline_driver)
                highlight_heading_and_paragraph(baseline_driver, record["tag"], record["baseline_title"])
                record["screenshot_baseline"] = capture_full_page_screenshot(baseline_driver, f"heading_{idx}_baseline.png")
            else:
                record["screenshot_baseline"] = ""
            
            if record["dev_title"] != "[missing]":
                dev_driver.get(DEV_URL)
                wait_for_document(dev_driver)
                highlight_heading_and_paragraph(dev_driver, record["tag"], record["dev_title"])
                record["screenshot_dev"] = capture_full_page_screenshot(dev_driver, f"heading_{idx}_dev.png")
            else:
                record["screenshot_dev"] = ""
        
    finally:
        baseline_driver.quit()
        dev_driver.quit()
    
    # Summary stats
    ctas_passed = sum(1 for c in cta_results if c.get("status") == "Passed")
    ctas_failed = sum(1 for c in cta_results if c.get("status") == "Failed")
    
    report_data = {
        "baseline_url": BASELINE_URL,
        "dev_url": DEV_URL,
        "heading_counts": heading_counts,
        "heading_comparisons": heading_comparisons,
        "cta_results": cta_results,
        "header_footer_ctas": header_footer_ctas,
        "ui_ux_screenshots": ui_ux_screenshots,
        "ui_ux_issues": ui_ux_issues_details,
        "ui_ux_issue_count": ui_ux_issue_count,
        "log_entries": log_entries,
        "page_screenshots": page_screenshots,
        "summary": {
            "headings_passed": headings_passed,
            "headings_failed": headings_failed,
            "ctas_passed": ctas_passed,
            "ctas_failed": ctas_failed,
            "ui_ux_issues": ui_ux_issue_count,
        },
    }
    generate_report(report_data, REPORT_FILE)
    print(f"\n[complete] Report generated: {REPORT_FILE}")


if __name__ == "__main__":
    main()
