import os
import pandas as pd
import altair as alt
from datetime import timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from io import StringIO

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

    # Access log page on PT -- Need to change the 4 digit for each term
    driver.get("https://us.prairietest.com/pt/center/1758/staff/log")
    
    # Wait for the logs (html table) to be present
    table = WebDriverWait(driver, WEB_DELAY).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-hover"))
    )

    # Use pandas to read the HTML table
    html_string = table.get_attribute('outerHTML')
    df = pd.read_html(StringIO(html_string))[0]

    # Filter rows containing "add session" (these contain the scheduled dates and locations)
    df = df[df.iloc[:, 1].str.contains("add session", case=False, na=False) & 
            ~df.iloc[:, 1].str.contains("add session label", case=False, na=False)]
    # ("add session label" is something else we want to ignore)

    # Extract date and location using regex
    df['Scheduled Date'] = df.iloc[:, 2].str.extract(r'^(.+?) \([A-Z]{3}\) added')
    df['Location'] = df.iloc[:, 2].str.extract(r'in (.+?) in CBTF')
    
    # Convert actions to +1 for "add session" and -1 for "deleted session"
    df['Action Value'] = df.iloc[:, 1].apply(
        lambda x: 1 if "add session" in x.lower() else (-1 if "deleted session" in x.lower() else 0)
    )
    
    # Convert Scheduled Date to pandas datetime
    df['Scheduled Date'] = pd.to_datetime(df['Scheduled Date'], format="%Y-%m-%d %H:%M:%S", errors='coerce')
    
    # Group by date and location, summing the Action Value
    grouped = df.groupby(['Scheduled Date', 'Location']).agg({'Action Value': 'sum'}).reset_index() 

    # Filter out sessions with net <= 0 (completely removed)
    df = grouped[grouped['Action Value'] > 0].drop(columns=['Action Value'])
    
    # Sort dates
    df.sort_values('Scheduled Date', inplace=True)
    
    # Keep only the relevant columns
    df = df[['Scheduled Date', 'Location']]

    # Print dataframe for testing
    print(df)

    # Save dataframe to .csv
    csv_path = os.path.join(os.getcwd(), 'schedule.csv')
    df.to_csv('schedule.csv')

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    driver.close()
    driver.quit()  # Close the browser
    
def visualize_test_session_heatmap(start_date, end_date):
    # Read data from the CSV file
    file_path = os.path.join(os.getcwd(), 'schedule.csv')
    df = pd.read_csv(file_path, parse_dates=['Scheduled Date'])

    # Convert Date, Hour
    df['Date'] = df['Scheduled Date'].dt.date
    df['Hour'] = df['Scheduled Date'].dt.hour

    # Group by Date, Hour, and Location, then count occurrences
    heatmap_data = df.groupby(['Date', 'Hour', 'Location']).size().reset_index(name='Count')
    heatmap_data['Date'] = pd.to_datetime(heatmap_data['Date'])

    # Debug: Check grouped data
    print("Grouped Data (heatmap_data):")
    print(heatmap_data.head(10))

    # Create full range of dates and hours
    full_hours = pd.DataFrame({'Hour': list(range(24))})
    full_dates = pd.DataFrame({'Date': pd.date_range(start=start_date, end=end_date)})
    full_locations = pd.DataFrame({'Location': heatmap_data['Location']})  # Add locations

    # Cross join full range of dates, hours, and locations
    full_grid = full_dates.merge(full_hours, how='cross').merge(full_locations, how='cross')

    # Merge full grid with expanded data
    heatmap_data = full_grid.merge(heatmap_data, on=['Date', 'Hour', 'Location'], how='left').fillna(0)
    heatmap_data['Count'] = heatmap_data['Count'].astype(int)

    # Create heatmap
    heatmap = alt.Chart(heatmap_data).mark_rect().encode(
        x=alt.X('Hour:O', title='Hour of Day'),
        y=alt.Y('Date:T', title='Date', timeUnit='yearmonthdate'),
        color=alt.Color('Count:Q', scale=alt.Scale(scheme='reds'), title='Session Counts'),
        tooltip=['Date:T', 'Hour:O', 'Location:N', 'Count:Q']
    ).properties(
        title='Test Session Heatmap',
        width=800,
        height=400
    ).facet(
        row=alt.Row('Location:N', title='Location')
    )

    return heatmap

if __name__ == "__main__":
    try:
        heatmap_chart = visualize_test_session_heatmap("2025-02-01", "2025-02-18")
        heatmap_path = os.path.join(os.getcwd(), 'test_session_heatmap.html')
        heatmap_chart.save(heatmap_path)
        print(f"Heatmap saved as '{heatmap_path}'. Open this file in your browser to view the chart.")
    except Exception as e:
        print(f"An error occurred while generating the heatmap: {e}")