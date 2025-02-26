import streamlit as st
import requests
import re
import time
import json
import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pytesseract
from PIL import Image


# ---- LOAD ENVIRONMENT VARIABLES ----
load_dotenv()

KLEINANZEIGEN_URL = os.getenv("KLEINANZEIGEN_URL")
GROK_API_KEY = os.getenv("GROK_API_KEY")
GOOGLE_LENS_API_KEY = os.getenv("GOOGLE_LENS_API_KEY")
CHRONO24_API_KEY = os.getenv("CHRONO24_API_KEY")
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH")

# Set up Selenium WebDriver
def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")
    service = Service(ChromeDriverManager().install()) # Update path
    driver = webdriver.Chrome(service=service, options=options)
    return driver

# Scrape Kleinanzeigen Watch Listings
def scrape_kleinanzeigen():
    driver = get_driver()
    driver.get(KLEINANZEIGEN_URL)
    time.sleep(2)
    listings = []
    elements = driver.find_elements(By.CLASS_NAME, "aditem")[:5]
    st.write(f"Found {len(elements)} listings")
    for el in elements:
        try:
            title = el.find_element(By.CLASS_NAME, "text-module-begin").text
            img_url = el.find_element(By.TAG_NAME, "img").get_attribute("src")
            price_element = el.find_element(By.CLASS_NAME, "aditem-main--middle--price-shipping--price")
            price_text = price_element.text.strip()
            price = re.sub(r"\D", "", price_text)  if price_text else "N/A"
            price = int(price) if price.isdigit() else 0
            details_url = el.find_element(By.TAG_NAME, "a").get_attribute("href")
            listings.append({"title": title, "img_url": img_url, "price": price, "details_url": details_url})
        except Exception as e:
            st.write(f"Error extracting data: {e}")
            continue
    driver.quit()
    return listings


# Extract Watch Details using Grok AI
def extract_watch_details(image_url):
    grok_api_url = "https://api.grok.com/analyze"
    headers = {"Authorization": f"Bearer {GROK_API_KEY}"}
    payload = {"image_url": image_url}
    try:
        response = requests.post(grok_api_url, headers=headers, json=payload)
        data = response.json()
        return {
            "brand": data.get("brand", "Unknown"),
            "model": data.get("model", "Unknown"),
            "dial_color": data.get("dial_color", "Unknown"),
            "case_material": data.get("case_material", "Unknown"),
            "reference_number": data.get("reference_number", "Unknown"),
        }
    except:
        return {"brand": "Unknown", "model": "Unknown", "dial_color": "Unknown", "case_material": "Unknown", "reference_number": "Unknown"}


# Extract Reference Number using Google Lens API
def extract_reference_number(image_url):
    google_lens_api_url = "https://vision.googleapis.com/v1/images:annotate"
    headers = {"Authorization": f"Bearer {GOOGLE_LENS_API_KEY}"}
    payload = {
        "requests": [{
            "image": {"source": {"imageUri": image_url}},
            "features": [{"type": "TEXT_DETECTION"}]
        }]
    }
    try:
        response = requests.post(google_lens_api_url, headers=headers, json=payload)
        data = response.json()
        ref_number = data["responses"][0]["textAnnotations"][0]["description"]
        return ref_number.strip()
    except:
        return "Unknown"

# Get VK Price from Chrono24 API
def get_chrono24_price(reference_number):
    chrono24_api_url = f"https://api.chrono24.com/prices/{reference_number}"
    headers = {"Authorization": f"Bearer {CHRONO24_API_KEY}"}
    try:
        response = requests.get(chrono24_api_url, headers=headers)
        data = response.json()
        return data.get("avg_price", 12000)
    except:
        return 12000

# Calculate EK Price
def calculate_ek(vk_price):
    return round(0.8 * vk_price / (1 + 2 * (2.71828 ** (-0.0002 * vk_price))), 2)

# ---- STREAMLIT UI ----
st.title("📌 Watch Price Automation POC")
st.subheader("🚀 Scraping Kleinanzeigen & Analyzing Prices")
listings = scrape_kleinanzeigen()

for listing in listings:
    st.image(listing["img_url"], width=150)
    st.write(f"**Title:** {listing['title']}")
    st.write(f"💰 **Price on Kleinanzeigen:** €{listing['price']}")
    # st.write(f"Scraped Listings: {listings}")
    #st.write(f"🔍 **Details:** {listing['details_url']}")
    
    details = extract_watch_details(listing["img_url"])
    reference_number = extract_reference_number(listing["img_url"])
    chrono24_price = get_chrono24_price(reference_number)
    ek_price = calculate_ek(chrono24_price)
    
    st.write(f"🕰 **Brand:** {details['brand']}")
    # st.write(f"📌 **Reference Number:** {reference_number}")
    # st.write(f"📊 **VK Price on Chrono24:** €{chrono24_price}")
    # st.write(f"🔢 **Calculated EK Price:** €{ek_price}")

    if listing["price"] <= ek_price:
        st.success(f"✅ **Good Deal! Consider buying for €{listing['price']}**")
    else:
        st.warning(f"❌ **Too Expensive. Should be €{ek_price} or lower.")

    # ✅ Fix KeyError by using 'details_url' instead of 'url'
    st.write(f"[🔗 LINKS ]({listing['details_url']})")
    st.markdown("---")
