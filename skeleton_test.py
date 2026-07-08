from playwright.sync_api import sync_playwright
from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

url ='https://swappko.com/'
output_dir = 'data/raw/'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto(url)
    print(page.title())

    page_name = url.split('/')[-2].split('.')[0]

    html_content = page.content()
    print(html_content[:500])
    with open(f'{output_dir}{page_name}_html_content.html','w',encoding='utf-8') as f:
        f.write(html_content)

    html_text = page.inner_text('body')
    with open(f'{output_dir}{page_name}_html_text.txt','w',encoding='utf-8') as f:
        f.write(html_text)

    page.screenshot(path=f'{output_dir}{page_name}_snapshot.png',full_page=True)

    browser.close()

client=genai.Client()
model = 'gemini-3.1-flash-lite'
contents = f"""
You are an expert analyst specializing in dark patterns — manipulative design tactics that e-commerce websites use to influence customer behavior. 
You will be given the visible text extracted from a web page. Identify any dark patterns present in the text. 
For each one, produce a short report entry naming the pattern, and describing how and where it appears. 
If you find no manipulative patterns, state that clearly rather than inventing any.

--- PAGE TEXT ---
{html_text}
"""

response = client.models.generate_content(
    model = model,
    contents = contents
)

report = response.text

import psycopg

screenshot_path  = f'{output_dir}{page_name}_snapshot.png'
html_path =  f'{output_dir}{page_name}_html_content.html'

with psycopg.connect(os.getenv('DATABASE_URL')) as conn:
    with conn.cursor() as cur:

        cur.execute("""
        INSERT INTO scans (url,html_pointer,screenshot_pointer,llm_report) VALUES
        (%s,%s,%s,%s)
        """,(url,html_path,screenshot_path,report))

        conn.commit()