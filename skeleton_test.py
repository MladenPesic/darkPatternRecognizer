from playwright.sync_api import sync_playwright
from google import genai
from dotenv import load_dotenv
import os
import psycopg
from supabase import Client, create_client
from classifier import predict
import logging
import subprocess

load_dotenv(override=True)

os.makedirs('logs',exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def capture_page(page):
    page.wait_for_load_state('load', timeout=60000)
    extracted_data = page.eval_on_selector_all(
        'button, a, h1, h2, h3, h4, h5, h6, p, span, div, label, li, small, strong, em',
        r'''els => els.map(el => {
            const r = el.getBoundingClientRect();
            const isVisible = r.width > 0 && r.height > 0;

            const hasTextChild = Array.from(el.children).some(
                c => c.innerText && c.innerText.trim() !== ''
            );
            if (hasTextChild) return null;

            const text = (el.innerText || '').replace(/\s+/g, ' ').trim();
            if (!text || text.length > 500) return null;

            return {
                tag: el.tagName.toLowerCase(),
                text: text,
                x: isVisible ? r.left + window.pageXOffset : null,
                y: isVisible ? r.top + window.pageYOffset : null,
                width:  isVisible ? r.width  : null,
                height: isVisible ? r.height : null
            };
        }).filter(Boolean)'''
    )

    html_content = page.content()
    html_text = page.inner_text('body')
    screenshot = page.screenshot(full_page=True)
    return html_text, html_content, screenshot, extracted_data

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

def classify_elements(extracted_data):
    for e in extracted_data:
        text = e['text']
        if text:
            label, probability = predict(text)
            e['label'] = label
            e['probability'] = probability
        else:
            e['label'] = None
            e['probability'] = None


def insert_elements(new_id,extracted_data):

    elements_to_insert = [(new_id,e['tag'],e['text'],e['x'],e['y'],e['width'],e['height'],e['label'],e['probability']) for e in extracted_data]

    with psycopg.connect(os.getenv('DATABASE_URL')) as conn:
        with conn.cursor() as cur:
            cur.executemany("""
            INSERT INTO elements (scan_id,element_type,element_text,geometry_x,geometry_y,geometry_width,geometry_height,darkpattern_label,confidence)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,elements_to_insert)

def process_page(page,model):
    new_id = insert_scan_row(page.url)
    logger.info('Scan %s started for %s',new_id,page.url)
    try:
        logger.info('Scan %s capturing DOM...', new_id)
        html_text,html_content,screenshot,extracted_data = capture_page(page)
        logger.info('Scan %s fetched %d elements',new_id,len(extracted_data))

        report = get_llm_report(model,html_text)
        html_pointer,screenshot_pointer = upload_files_to_storage(html_content,screenshot,new_id)
        classify_elements(extracted_data)
        logger.info('Scan %s classified elements',new_id)

        insert_elements(new_id,extracted_data)
        update_scan_row(html_pointer,screenshot_pointer,report,new_id,'completed')
        logger.info('Scan %s completed',new_id)

    except Exception:
        logger.exception('Scan %s (%s) failed',new_id,page.url)
        mark_failed(new_id)

def main(url,model):
    text = r'"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\mladenp\chrome-debug-profile"'
    try:
        subprocess.Popen(text)
    except Exception:
        logger.exception("subprocess couldn't open")

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0]
        page.goto(url,wait_until='load',timeout=60000)
        page.wait_for_timeout(3000)
        while True:
            cmd = input('Navigate the browser, then Enter to capture or (close) to quit:')
            if cmd.strip().lower() == 'close':
                break
            process_page(page,model)


if __name__ == '__main__':
    model = 'gemini-3.5-flash-lite'
    url = 'https://www.burlington.com/'
    main(url,model)

