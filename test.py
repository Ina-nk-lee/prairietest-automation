import os
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
import altair as alt

WEB_DELAY = 100

CWL_USERNAME = "REDIRECTED"
CWL_PASSWORD = "REDIRECTED"

# Create Chrome profile in same directory to retain 2FA
profile_path = os.path.join(os.path.dirname(__file__), "chrome_profile")

# Append Chrome profile options to current session
options = webdriver.ChromeOptions()
options.add_argument(f"user-data-dir={profile_path}")

# Start Chrome
driver = webdriver.Chrome(options=options)

def visualize_heatmap(start_date, end_date):
    # Read data from the CSV file
    file_path = 'schedule.csv'
    df = pd.read_csv(file_path)
    print('reached phase 1')

    # Convert StartTime and EndTime to datetime
    df['Scheduled Date'] = pd.to_datetime(df['Scheduled Date'])
    

    # Expand rows to include every relevant hour
    expanded_rows = []
    for _, row in df.iterrows():
        current_time = row['Scheduled Date']

        if '014' in row['Location']:
            expanded_rows.append({'Date': current_time.date(), 'Hour': current_time.hour, 'Location': '014'})
        elif '008' in row['Location']:
            expanded_rows.append({'Date': current_time.date(), 'Hour': current_time.hour, 'Location': '008'})
    
    print('reached phase 2')

    # Create expanded DataFrame
    expanded_df = pd.DataFrame(expanded_rows)
    expanded_df['Date'] = pd.to_datetime(expanded_df['Date']) 

    # Group by Date, Hour, and Location, then count occurrences
    heatmap_data = expanded_df.groupby(['Date', 'Hour', 'Location']).size().reset_index(name='Count')

    # Debug: Check grouped data
    print("Grouped Data (heatmap_data):")
    print(heatmap_data.head(10))

    # Create full range of dates and hours
    full_hours = pd.DataFrame({'Hour': list(range(24))})
    full_dates = pd.DataFrame({'Date': pd.date_range(start=start_date, end=end_date)})
    full_locations = pd.DataFrame({'Location': ['014', '008']})  # Add locations

    # Cross join full range of dates, hours, and locations
    full_grid = full_dates.merge(full_hours, how='cross').merge(full_locations, how='cross')

    # Merge full grid with expanded data
    heatmap_data = full_grid.merge(heatmap_data, on=['Date', 'Hour', 'Location'], how='left').fillna(0)
    heatmap_data['Count'] = heatmap_data['Count'].astype(int)

    # Create heatmap
    heatmap = alt.Chart(heatmap_data).mark_rect().encode(
        x=alt.X('Hour:O', title='Hour of Day'),
        y=alt.Y('Date:T', title='Date', timeUnit='yearmonthdate'),
        color=alt.Color('Count:Q', scale=alt.Scale(scheme='blues'), title='Number of Sessions'),
        tooltip=['Date:T', 'Hour:O', 'Location:N', 'Count:Q']
    ).properties(
        title='Prairetest Sessions Heatmap',
        width=800,
        height=400
    ).facet(
        row=alt.Row('Location:N', title='Location')
    )

    return heatmap

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
    driver.get("https://us.prairietest.com/pt/center/1758/staff/log") #CBTF 2024W2
    
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
    

    alt.renderers.enable('mimetype')
    heatmap_chart = visualize_heatmap("2025-02-01", "2025-02-10")
    heatmap_chart.show() 
    heatmap_chart.save('heatmap.html')
    print("Heatmap saved as 'heatmap.html'. Open this file in your browser to view the chart.")


except Exception as e:
    print("An error occurred:", e)

finally:
    driver.close()
    driver.quit()  # Close the browser

