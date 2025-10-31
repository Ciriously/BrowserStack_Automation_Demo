from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import requests
from googletrans import Translator
import re
from collections import Counter

# === START OF STEP 1 CODE ===
print("Starting the script...")
driver_service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=driver_service)
opinion_url = "https://elpais.com/opinion/"
driver.get(opinion_url)
print(f"Opened {opinion_url}")
time.sleep(3)
# === END OF STEP 1 CODE ===


# === START OF STEP 2 CODE ===
print("Scraping the first 5 article links...")
selector = "h2 a"
article_elements = driver.find_elements(By.CSS_SELECTOR, selector)[:5]
article_urls = [el.get_attribute('href') for el in article_elements]
print(f"Found {len(article_urls)} article URLs:")
print(article_urls)
# === END OF STEP 2 CODE ===


# === START OF STEP 3 CODE ===
print("\n--- Starting Step 3: Scraping individual articles ---")
spanish_titles = []
all_spanish_content = []

for i, url in enumerate(article_urls):
    print(f"\n--- Scraping Article {i+1}: {url} ---")
    driver.get(url)
    time.sleep(2)

    # --- 3A. GET TITLE (Spanish) ---
    try:
        title = driver.find_element(By.TAG_NAME, "h1").text
        print(f"TITLE (ES): {title}")
        spanish_titles.append(title)
    except Exception as e:
        print(f"Could not find title: {e}")
        spanish_titles.append(None)

    # --- 3B. GET CONTENT (Spanish) ---
    try:
        content_body = driver.find_element(
            By.CSS_SELECTOR, "div.c-article-body")
        paragraphs = content_body.find_elements(By.TAG_NAME, "p")
        full_content = "\n".join([p.text for p in paragraphs])
        all_spanish_content.append(full_content)
        print(f"CONTENT (ES) Snippet:\n{full_content[:200]}...")
    except Exception as e:
        print(f"Could not find content: {e}")

    # --- 3C. DOWNLOAD IMAGE ---
    try:
        image_element = driver.find_element(By.CSS_SELECTOR, "figure img")
        image_url = image_element.get_attribute('src')
        if image_url:
            response = requests.get(image_url)
            if response.status_code == 200:
                filename = f"article_image_{i+1}.jpg"
                with open(filename, 'wb') as f:
                    f.write(response.content)
                print(f"SUCCESS: Saved image to {filename}")
            else:
                print(
                    f"WARN: Could not download image, status: {response.status_code}")
    except Exception as e:
        print(f"WARN: Could not find or save image: {e}")
# === END OF STEP 3 CODE ===


# === START OF PART 2: TRANSLATE HEADERS ===
print("\n--- Starting Part 2: Translating Headers ---")
valid_spanish_titles = [title for title in spanish_titles if title]
translator = Translator()
english_titles = []
for title in valid_spanish_titles:
    try:
        translated = translator.translate(title, src='es', dest='en')
        print(f"ES: {title}")
        print(f"EN: {translated.text}")
        english_titles.append(translated.text)
    except Exception as e:
        print(f"Error translating '{title}': {e}")
# === END OF PART 2 ===


# === START OF PART 3: ANALYZE HEADERS ===
print("\n--- Starting Part 3: Analyzing Translated Headers ---")
if english_titles:
    all_headers_text = " ".join(english_titles)
    cleaned_text = re.sub(r'[^\w\s]', '', all_headers_text.lower())
    words = cleaned_text.split()
    stop_words = {'a', 'an', 'the', 'in', 'on', 'of',
                  'for', 'to', 'is', 'and', 'with', 'it', 'by'}
    filtered_words = [word for word in words if word not in stop_words]
    word_counts = Counter(filtered_words)
    print("Repeated Words (more than 2 times, ignoring stop words):")
    found_repeated_words = False
    for word, count in word_counts.items():
        if count > 2:
            print(f"- '{word}': {count} times")
            found_repeated_words = True
    if not found_repeated_words:
        print("No significant words were repeated more than twice.")
else:
    print("No titles were translated, skipping analysis.")
# === END OF PART 3 ===


print("\nScript finished scraping, translating, and analyzing.")
driver.quit()
