import os
import pandas as pd
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Define the profile path relative to the script's working directory
profile_path = os.path.join(os.path.dirname(__file__), "chrome_profile")

# Set up Chrome options to use the profile path
options = webdriver.ChromeOptions()
options.add_argument(f"user-data-dir={profile_path}")

# Start Chrome with the specified profile
driver = webdriver.Chrome(options=options)

try:
    driver.get("https://us.prairielearn.com/pl/auth/institution/781/saml/login")
    
    # The rest of your script for logging in, checking the logs, etc.
    WebDriverWait(driver, 100).until(EC.url_contains("SAML2"))

    # Input credentials on the university SSO page
    username_field = WebDriverWait(driver, 100).until(
        EC.presence_of_element_located((By.ID, "username"))
    )
    username_field.send_keys("USERNAME_REDACTED") 

    password_field = driver.find_element(By.ID, "password")
    password_field.send_keys("PASSCODE_REDACTED") 
    password_field.send_keys(Keys.RETURN)

    # Wait for either the 2FA button or the successful redirection
    WebDriverWait(driver, 100).until(
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
        WebDriverWait(driver, 100).until(EC.url_contains("us.prairielearn.com/pl"))
    
    # At this point, we should be logged in, regardless of whether 2FA was required

    # Proceed with accessing the logs
    driver.get("https://us.prairietest.com/pt/center/1362/staff/log")
    
    # Wait for the table to be present
    table = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-hover"))
    )

    # Dictionary to store session data
    session_data = []

    # Find all rows in the table
    rows = table.find_elements(By.TAG_NAME, "tr")

    # Iterate through each row
    for row in rows:
        # Find all td elements in this row
        tds = row.find_elements(By.TAG_NAME, "td")
        
        # Check if this row has at least 3 td elements
        if len(tds) >= 3:
            # Check if the second td contains "add session"
            second_td = tds[1]
            span = second_td.find_element(By.TAG_NAME, "span")
            if "add session" in span.text.lower() and "add session label" not in span.text.lower():
                log_text = tds[2].text
                
                # Extract date using regex
                date_pattern = r'^(.+?) \([A-Z]{3}\) added'
                date_match = re.match(date_pattern, log_text)
                if date_match:
                    date_added = date_match.group(1).strip()
                else:
                    date_added = None  # Handle as needed

                # Extract location using regex
                location_pattern = r'in (.+?) in CBTF'
                location_match = re.search(location_pattern, log_text)
                if location_match:
                    location = location_match.group(1).strip()
                else:
                    location = "Unknown"
                
                # Add date and location to the dictionary
                session_data.append({
                    "Date Added": date_added,
                    "Location" : location
                    }
                )
    
    # Convert the dictionary to pandas dataframe
    df = pd.DataFrame(session_data)

    # Convert Date Added to pandas' datetime
    df['Date Added'] = pd.to_datetime(df['Date Added'], format="%Y-%m-%d %H:%M:%S", errors='coerce')
    
    # Sort Date Added
    df.sort_values('Date Added', inplace = True)

    # Print the dataframe for testing
    print(df)

except Exception as e:
    print("An error occurred:", e)

finally:
    driver.quit()  # Close the browser