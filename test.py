import os
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

WEB_DELAY = 100

CWL_USERNAME = "REDACTED"
CWL_PASSWORD = "REDACTED"

# Create Chrome profile in same directory to retain 2FA
profile_path = os.path.join(os.path.dirname(__file__), "chrome_profile")

# Append Chrome profile options to current session
options = webdriver.ChromeOptions()
options.add_argument(f"user-data-dir={profile_path}")

# Start Chrome
driver = webdriver.Chrome(options=options)

try:
    driver.get("https://us.prairielearn.com/pl/auth/institution/781/saml/login")
    
    # Wait for UBC CWL login
    WebDriverWait(driver, WEB_DELAY).until(EC.url_contains("SAML2"))

    # Input your credentials
    username_field = WebDriverWait(driver, WEB_DELAY).until(
        EC.presence_of_element_located((By.ID, "username"))
    )
    username_field.send_keys(CWL_USERNAME) 

    password_field = driver.find_element(By.ID, "password")
    password_field.send_keys(CWL_PASSWORD) 
    password_field.send_keys(Keys.RETURN)

    # Wait for either the 2FA button or the successful redirection
    WebDriverWait(driver, WEB_DELAY).until(
        EC.any_of(
            EC.element_to_be_clickable((By.ID, "trust-browser-button")),
            EC.url_contains("us.prairielearn.com/pl")
        )
    )

    # Check if we're on the 2FA page
    if "duo" in driver.current_url:
        duo_button = driver.find_element(By.ID, "trust-browser-button")
        duo_button.click()
        # Wait for the redirection after 2FA
        WebDriverWait(driver, WEB_DELAY).until(EC.url_contains("us.prairielearn.com/pl"))
    
    # At this point we should be logged in

    # Access log page on PT
    driver.get("https://us.prairietest.com/pt/center/1362/staff/log")
    
    # Wait for the logs (html table) to be present
    table = WebDriverWait(driver, WEB_DELAY).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-hover"))
    )

    # Use pandas to read the HTML table
    df = pd.read_html(table.get_attribute('outerHTML'))[0]

    # Filter rows containing "add session" (these contain the scheduled dates and locations)
    df = df[df.iloc[:, 1].str.contains("add session", case=False, na=False) & 
            ~df.iloc[:, 1].str.contains("add session label", case=False, na=False)]
    
    # ("add session label" is something else we want to ignore)

    # Extract date and location using regex
    df['Scheduled Date'] = df.iloc[:, 2].str.extract(r'^(.+?) \([A-Z]{3}\) added')
    df['Location'] = df.iloc[:, 2].str.extract(r'in (.+?) in CBTF')

    # Convert Scheduled Date to pandas datetime
    df['Scheduled Date'] = pd.to_datetime(df['Scheduled Date'], format="%Y-%m-%d %H:%M:%S", errors='coerce')
    
    # Sort dates
    df.sort_values('Scheduled Date', inplace=True)

    # Keep only the relevant columns
    df = df[['Scheduled Date', 'Location']]

    # Print dataframe for testing
    print(df)

    # Save dataframe to .csv
    df.to_csv('schedule.csv')

except Exception as e:
    print("An error occurred:", e)

finally:
    driver.close()
    driver.quit()  # Close the browser