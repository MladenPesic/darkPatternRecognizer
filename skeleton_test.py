from playwright.sync_api import sync_playwright
from google import genai
from dotenv import load_dotenv
import os
import psycopg
from supabase import Client, create_client


load_dotenv(override=True)

def fetch_url(url:str):

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url)

        html_content = page.content()
        html_text = page.inner_text('body')
        screenshot = page.screenshot(full_page=True)

        browser.close()
    return  html_text,html_content,screenshot

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

def upload_files_to_storage(html_content,screenshot,new_id):
    supabase_url = os.getenv('SUPABASE_PROJECT_URL')
    supabase_key = os.getenv('SUPABASE_KEY')

    supabase:Client = create_client(supabase_url,supabase_key)

    html_bytes = html_content.encode('utf-8')

    files_to_upload = [
        (html_bytes,'html.html'),
        (screenshot,'screenshot.png')
    ]

    path_pointers = []
    for data,extension in files_to_upload:
        response = supabase.storage.from_('scans').upload(
            path = f'{new_id}_{extension}',
            file = data,
            file_options={'cache-control':'3600','upsert':'false'}
        )
        path_pointers.append(response.fullPath)
    return path_pointers


def insert_scan_row(url):
    with psycopg.connect(os.getenv('DATABASE_URL')) as conn:
        with conn.cursor() as cur:

            cur.execute("""
            INSERT INTO scans (url) VALUES
            (%s) RETURNING id
            """,(url,))

            row = cur.fetchone()
            new_id = row[0]
            return new_id

def update_scan_row(html_pointer,screenshot_pointer,report,new_id,status):
    with psycopg.connect(os.getenv('DATABASE_URL')) as conn:
        with conn.cursor() as cur:

            cur.execute("""
            UPDATE scans
            SET 
                html_pointer = %s,
                screenshot_pointer = %s,
                llm_report = %s,
                status = %s
            WHERE id = %s
            """,(html_pointer,screenshot_pointer,report,status,new_id))

def mark_failed(new_id):
    with psycopg.connect(os.getenv('DATABASE_URL')) as conn:
        with conn.cursor() as cur:

            cur.execute("""
            UPDATE scans
            SET status = 'failed'
            WHERE id = %s
            """,(new_id,))

def main(url,model):
    new_id = insert_scan_row(url)
    try:
        html_text,html_content,screenshot = fetch_url(url)
        report = get_llm_report(model,html_text)
        html_pointer,screenshot_pointer = upload_files_to_storage(html_content,screenshot,new_id)
        update_scan_row(html_pointer,screenshot_pointer,report,new_id,'completed')
        print(f'Database updated with the report: \n\n {report}')
    except Exception as e:
        print(e)
        mark_failed(new_id)


if __name__ == '__main__':
    url = 'https://swappko.com/'
    model = 'gemini-3.1-flash-lite'
    main(url,model)

