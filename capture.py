from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os
import psycopg
from supabase import Client, create_client
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

            const hasTextChild = Array.from(el.children).some(
                c => c.innerText && c.innerText.trim() !== ''
            );
            if (hasTextChild) return null;

            const text = (el.innerText || '').replace(/\s+/g, ' ').trim();
            if (!text || text.length > 500) return null;

            return {
                tag: el.tagName.toLowerCase(),
                text: text,
                x: r.left + window.pageXOffset,
                y: r.top + window.pageYOffset,
                width: r.width,
                height: r.height
            };
        }).filter(Boolean)'''
    )

    dims = page.evaluate("""() => ({
        page_width: document.documentElement.scrollWidth,
        page_height: document.documentElement.scrollHeight
    })""")

    html_content = page.content()
    return html_content, extracted_data, dims

def upload_files_to_storage(html_content,new_id):
    supabase_url = os.getenv('SUPABASE_PROJECT_URL')
    supabase_key = os.getenv('SUPABASE_KEY')

    supabase:Client = create_client(supabase_url,supabase_key)

    html_bytes = html_content.encode('utf-8')

    response = supabase.storage.from_('scans').upload(
        path = f'{new_id}_html.html',
        file = html_bytes,
        file_options={'cache-control':'3600','upsert':'false'}
    )

    return response.fullPath


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

def update_scan_row(html_pointer,new_id,status,dims):
    with psycopg.connect(os.getenv('DATABASE_URL')) as conn:
        with conn.cursor() as cur:

            cur.execute("""
            UPDATE scans
            SET 
                html_pointer = %s,
                status = %s,
                page_width=%s,
                page_height=%s
            WHERE id = %s
            """,(html_pointer,status,dims['page_width'],dims['page_height'],new_id))

def mark_failed(new_id):
    with psycopg.connect(os.getenv('DATABASE_URL')) as conn:
        with conn.cursor() as cur:

            cur.execute("""
            UPDATE scans
            SET status = 'failed'
            WHERE id = %s
            """,(new_id,))


def insert_elements(new_id,extracted_data):

    elements_to_insert = [(new_id,e['tag'],e['text'],e['x'],e['y'],e['width'],e['height']) for e in extracted_data]

    with psycopg.connect(os.getenv('DATABASE_URL')) as conn:
        with conn.cursor() as cur:
            cur.executemany("""
            INSERT INTO elements (scan_id,element_type,element_text,geometry_x,geometry_y,geometry_width,geometry_height)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,elements_to_insert)

def process_page(page):
    new_id = insert_scan_row(page.url)
    logger.info('Scan %s started for %s',new_id,page.url)
    try:
        logger.info('Scan %s capturing DOM...', new_id)
        html_content,extracted_data,dims = capture_page(page)
        logger.info('Scan %s fetched %d elements',new_id,len(extracted_data))

        html_pointer = upload_files_to_storage(html_content,new_id)

        insert_elements(new_id,extracted_data)
        update_scan_row(html_pointer,new_id,'completed',dims)
        logger.info('Scan %s completed',new_id)

    except Exception:
        logger.exception('Scan %s (%s) failed',new_id,page.url)
        mark_failed(new_id)

def main(url):
    chrome_path = os.getenv('CHROME_PATH')
    chrome_profile=os.getenv('CHROME_PROFILE')
    command = [chrome_path,'--remote-debugging-port=9222',f'--user-data-dir={chrome_profile}']
    try:
        subprocess.Popen(command)
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
            process_page(page)


if __name__ == '__main__':
    url='https://www.shein.com'
    main(url)

