
# This script executes a multi-step web automation task in parallel.
# It scrapes El País, translates headlines, and analyzes text,
# running the entire workflow across 5 different cloud browsers on BrowserStack.
#
# It's built to be secure (using .env) and robust (using explicit waits).

import threading
import os
import re
from collections import Counter
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from googletrans import Translator
from dotenv import load_dotenv

# -----------------------------------------------------------------
# --- SECTION 1: CONFIGURATION & CREDENTIALS ---
# -----------------------------------------------------------------

# Load key-value pairs from our .env file into the script's os environment
# This is how we keep secret keys out of the code (good security practice).
load_dotenv()

# Read the credentials from the environment.
# os.environ.get() is 'safe' - it returns None if the key doesn't exist.
BS_USER = os.environ.get("BS_USER")
BS_KEY = os.environ.get("BS_KEY")

# Fail-fast. If the keys aren't set, stop the script and tell the user why.
if not BS_USER or not BS_KEY:
    print("Error: BrowserStack credentials (BS_USER, BS_KEY) are not set.")
    print("Please create a .env file and add your credentials to it.")
    exit()  # Stop execution.

# This is the remote Selenium Grid URL for BrowserStack.
# The `https` protocol is required for the connection.
hub_url = f"https://{BS_USER}:{BS_KEY}@hub-cloud.browserstack.com/wd/hub"

print("Credentials loaded successfully from .env file.")

# -----------------------------------------------------------------
# --- SECTION 2: TEST ENVIRONMENTS (THE 'MATRIX') ---
# -----------------------------------------------------------------
#
# Define the 5 browser/OS/device combinations we want to test against.
# These dictionaries are 'capabilities' that BrowserStack uses to build
# the correct test environment.
#
all_capabilities = [
    {
        'browserName': 'Chrome',
        'browserVersion': 'latest',
        'bstack:options': {
            "os": "Windows", "osVersion": "11",
            "sessionName": "El Pais Scraper - Win11/Chrome"
        }
    },
    {
        'browserName': 'Safari',
        'browserVersion': 'latest',
        'bstack:options': {
            "os": "OS X", "osVersion": "Sonoma",
            "sessionName": "El Pais Scraper - macOS/Safari"
        }
    },
    {
        'browserName': 'Firefox',
        'browserVersion': 'latest',
        'bstack:options': {
            "os": "Windows", "osVersion": "10",
            "sessionName": "El Pais Scraper - Win10/Firefox"
        }
    },
    {
        'browserName': 'Safari',
        'bstack:options': {
            "deviceName": "iPhone 14 Pro", "osVersion": "16",
            "realMobile": "true",
            "sessionName": "El Pais Scraper - iPhone 14 Pro"
        }
    },
    {
        'browserName': 'Chrome',
        'bstack:options': {
            "deviceName": "Samsung Galaxy S23", "osVersion": "13.0",
            "realMobile": "true",
            "sessionName": "El Pais Scraper - Galaxy S23"
        }
    }
]


# -----------------------------------------------------------------
# --- SECTION 3: THE CORE AUTOMATION LOGIC ---
# -----------------------------------------------------------------

def run_scrape_test(caps):
    """
    This is the main function that each thread will run.
    It encapsulates the entire test: setup, execution, and teardown.
    'caps' is the dictionary for a single browser (from all_capabilities).
    """

    # Grab info for logging, with fallbacks just in case.
    session_name = caps.get('bstack:options', {}).get(
        'sessionName', 'Unnamed Test')
    browser_name = caps.get('browserName', '').lower()
    print(f"--- STARTING TEST: {session_name} ---")

    # --- A. Build Browser 'Options' (Selenium 4 Style) ---
    # We must convert our 'caps' dictionary into a proper Options object
    # that `webdriver.Remote` expects.
    print(f"[{session_name}] Preparing options for {browser_name}...")
    options = None

    if 'chrome' in browser_name:
        options = webdriver.ChromeOptions()
    elif 'firefox' in browser_name:
        options = webdriver.FirefoxOptions()
    elif 'safari' in browser_name:
        options = webdriver.SafariOptions()
    else:
        # Fallback for any unknown config
        options = webdriver.ChromeOptions()

    # Loop through our capability dictionary and set them on the options object.
    for key, value in caps.items():
        if key == 'browserVersion':
            options.browser_version = value
        else:
            # `set_capability` is the universal way to add any key,
            # including the 'bstack:options' dictionary.
            options.set_capability(key, value)

    # --- End of Options block ---

    # We must declare `driver` outside the try block
    # so the `finally` block can access it for cleanup.
    driver = None

    try:
        # --- B. Connect to BrowserStack ---
        # This is the moment we "spin up" the remote browser.
        driver = webdriver.Remote(
            command_executor=hub_url,
            options=options
        )

        # Set up our intelligent wait strategy (10s max timeout).
        # This is *far* more reliable than `time.sleep()`.
        wait = WebDriverWait(driver, 10)

        # --- C. Navigate to Opinion Page ---
        driver.get("https://elpais.com/opinion/")
        print(f"[{session_name}] Navigated to opinion page.")

        # --- D. Get 5 Article Links ---
        # Tell Selenium to wait until the links are *actually visible*
        # before trying to find them.
        link_selector = "h2 a"
        wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, link_selector)))

        # Grab the first 5 elements matching the selector
        article_elements = driver.find_elements(
            By.CSS_SELECTOR, link_selector)[:5]
        article_urls = [el.get_attribute('href') for el in article_elements]
        print(f"[{session_name}] Found {len(article_urls)} URLs.")

        # --- E. Loop & Scrape Each Article ---
        spanish_titles = []
        for i, url in enumerate(article_urls):
            if not url:
                continue

            print(f"[{session_name}] Scraping article {i+1}...")
            driver.get(url)

            # 4A. Get Title
            try:
                # Wait for the <h1> tag to be loaded in the DOM.
                title_selector = "h1"
                wait.until(EC.presence_of_element_located(
                    (By.TAG_NAME, title_selector)))
                title = driver.find_element(By.TAG_NAME, title_selector).text
                spanish_titles.append(title)
                print(f"[{session_name}] Title: {title[:30]}...")
            except Exception:
                spanish_titles.append(None)

            # 4B. Get Content
            try:
                # Wait for the article body <div> to be loaded.
                content_selector = "div.c-article-body"
                wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, content_selector)))
                content_body = driver.find_element(
                    By.CSS_SELECTOR, content_selector)
                paragraphs = content_body.find_elements(By.TAG_NAME, "p")
                full_content = "\n".join([p.text for p in paragraphs])
                print(f"[{session_name}] Content snippet: {full_content[:50]}...")
            except Exception:
                # This often fails due to cookie banners/paywalls.
                # A more advanced script would find and click the "Accept" button here.
                print(f"[{session_name}] Could not find content body.")

            # 4C. Get Image
            try:
                # Wait for the main <img> to be visible.
                image_selector = "figure img"
                wait.until(EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, image_selector)))
                image_element = driver.find_element(
                    By.CSS_SELECTOR, image_selector)
                image_url = image_element.get_attribute('src')
                if image_url:
                    print(f"[{session_name}] Found image URL.")
            except Exception:
                print(f"[{session_name}] WARN: No image found for article {i+1}.")

        # --- F. Translate Headers ---
        print(f"[{session_name}] Translating titles...")
        # Filter out any 'None' titles
        valid_spanish_titles = [t for t in spanish_titles if t]
        translator = Translator()
        english_titles = []
        for title in valid_spanish_titles:
            try:
                translated = translator.translate(title, src='es', dest='en')
                english_titles.append(translated.text)
            except Exception as e:
                print(f"[{session_name}] Error translating a title: {e}")
        print(f"[{session_name}] Translated {len(english_titles)} titles.")

        # --- G. Analyze Headers ---
        print(f"[{session_name}] Analyzing titles...")
        if english_titles:
            all_headers_text = " ".join(english_titles)
            cleaned_text = re.sub(r'[^\w\s]', '', all_headers_text.lower())
            words = cleaned_text.split()

            # A simple 'stop word' list to filter out noise.
            stop_words = {'a', 'an', 'the', 'in', 'on', 'of',
                          'for', 'to', 'is', 'and', 'with', 'it', 'by'}
            filtered_words = [word for word in words if word not in stop_words]

            word_counts = Counter(filtered_words)

            found_repeated = False
            for word, count in word_counts.items():
                if count > 2:
                    print(
                        f"[{session_name}] REPEATED WORD: '{word}' ({count} times)")
                    found_repeated = True
            if not found_repeated:
                print(f"[{session_name}] No significant repeated words found.")

        # --- H. Mark Test as PASSED ---
        # This JS executor hook tells the BrowserStack dashboard
        # that the test completed successfully.
        driver.execute_script(
            'browserstack_executor: {"action": "setSessionStatus", "arguments": {"status":"passed", "reason": "Scraping and analysis complete!"}}'
        )

    except Exception as e:
        # --- I. Mark Test as FAILED ---
        # If any part of the 'try' block fails, we land here.
        print(f"--- TEST FAILED: {session_name} ---")
        print(f"ERROR: {e}")

        # Tell the BrowserStack dashboard the test failed and why.
        if driver:
            driver.execute_script(
                'browserstack_executor: {"action": "setSessionStatus", "arguments": {"status":"failed", "reason": f"Error: {e}"}}'
            )

    finally:
        # --- J. Teardown & Cleanup ---
        # This `finally` block runs *no matter what* (success or fail).
        # It's crucial for closing the remote browser to prevent zombie sessions.
        if driver:
            driver.quit()
        print(f"--- FINISHED TEST: {session_name} ---")

# -----------------------------------------------------------------
# --- SECTION 4: THREAD LAUNCHER ---
# -----------------------------------------------------------------


print("Starting 5 parallel tests on BrowserStack...")
threads = []

# Create and start one thread for each browser in our capability list.
for cap in all_capabilities:
    t = threading.Thread(target=run_scrape_test, args=(cap,))
    threads.append(t)
    t.start()

# This 'join' loop tells the main script to wait here until
# all 5 of the threads have finished their work.
for t in threads:
    t.join()

print("\n--- All 5 tests have completed. ---")
print("✅ Check your BrowserStack Automate dashboard to see results and videos.")
