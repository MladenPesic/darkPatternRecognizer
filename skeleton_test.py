from playwright.sync_api import sync_playwright
from google import genai
from dotenv import load_dotenv
import os
import psycopg

load_dotenv()

def fetch_url(url:str,output_dir='data/raw/'):

    output_dir = output_dir

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url)

        page_name = url.split('/')[-2].split('.')[0]

        html_content = page.content()

        html_path = f'{output_dir}{page_name}_html_content.html'
        with open(html_path,'w',encoding='utf-8') as f:
            f.write(html_content)

        html_text = page.inner_text('body')

        with open(f'{output_dir}{page_name}_html_text.txt','w',encoding='utf-8') as f:
            f.write(html_text)

        screenshot_path = f'{output_dir}{page_name}_snapshot.png'
        page.screenshot(path=screenshot_path,full_page=True)

        browser.close()
    return html_path, screenshot_path, html_text

def get_llm_report(model:str,html_text):

    client=genai.Client()

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
    return report

def update_database(url,html_path,screenshot_path,report):
    with psycopg.connect(os.getenv('DATABASE_URL')) as conn:
        with conn.cursor() as cur:

            cur.execute("""
            INSERT INTO scans (url,html_pointer,screenshot_pointer,llm_report) VALUES
            (%s,%s,%s,%s)
            """,(url,html_path,screenshot_path,report))

            conn.commit()

def main(url,model):
    html_path, screenshot_path, html_text = fetch_url(url)
    report = get_llm_report(model,html_text)
    update_database(url,html_path,screenshot_path,report)
    return print(f'Database updated with the report: \n\n {report}')

if __name__ == '__main__':
    url = 'https://swappko.com/'
    model = 'gemini-3.1-flash-lite'
    main(url,model)