from google import genai
from dotenv import load_dotenv
import os,time
import psycopg
import json
import logging

load_dotenv(override=True)

os.makedirs('logs',exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/label_elements.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def fetch_elements(only_unlabeled=False):
    query = """
        SELECT id, element_text
        FROM elements
        WHERE element_text IS NOT NULL
          AND TRIM(element_text) <> ''
          AND geometry_width IS NOT NULL
    """
    if only_unlabeled:
        query += " AND llm_label IS NULL"
    query += " ORDER BY element_text;"

    with psycopg.connect(os.getenv('DATABASE_URL')) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()

def llm_labeler(elements_batch,model):
    client = genai.Client()
    numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(elements_batch))
    contents =f"""
    You label web-page element texts for dark-pattern detection. A dark pattern is a manipulative
    TACTIC in the text: manufactured urgency/scarcity, engineered social pressure, confirmshaming/
    guilt, forced action, or misdirection. Judge the text ON ITS FACE. Neutral UI text and
    transparent offers are NOT dark patterns (e.g. "Add to cart" = 0, "Sale Price" = 0).
    If a mostly-benign product listing contains a tactic phrase (e.g. "Only few left"), label it 1.
    
    For EACH numbered element, return one JSON object:
    {{"index": <n>, "label": 0 or 1,
     "category": "urgency|scarcity|social_proof|confirmshaming|forced_action|misdirection|none",
     "reason": "<short justification>"}}
    Return a JSON array, nothing else.
    
    EXAMPLES:
    "Add to cart" -> 0, none (neutral UI)
    "Sale Price" -> 0, none (static label, no tactic)
    "Cyber Sale in July" -> 0, none (a sale's NAME is not a tactic)
    "Christmas in July Sale" -> 0, none (sale name)
    "Currently Trending" -> 0, none (section header, descriptive)
    "#1 Bestseller" -> 0, none (static badge, no pressure)
    "Free shipping on orders over $50" -> 0, none (transparent offer)
    "Hurry! These savings end soon" -> 1, urgency (manufactured time pressure)
    "Limited-Time Offer until 7/23" -> 1, urgency (explicit deadline pressure)
    "Sale ends in 09:59" -> 1, urgency (countdown)
    "Hot Deal" -> 1, urgency (manufactured deal urgency)
    "Lowest price since launch" -> 1, urgency (manufactured deal urgency)
    "Only few left" -> 1, scarcity (low-stock pressure)
    "Chain Bracelet RSD204.69 RSD309.66 7 bought this" -> 0, none (static cumulative total)
    "Gel Heel Protectors 158 RSD 400K+ sold -64% 4.8 stars" -> 0, none (lifetime total, no timeframe)
    "3 people bought this in the last hour" -> 1, social_proof (recency-framed activity)
    "127 people are viewing this right now" -> 1, social_proof (live activity pressure)
    "Selling fast" -> 1, social_proof (implied live demand)
    "No thanks, I'll pay full price" -> 1, confirmshaming (guilt-framed decline)
    "CABRRR Straight Fit Men Grey Jeans 69% off 1,299 396 3.9 (203) Only few left" -> 1, scarcity
      (mostly-benign listing with an embedded tactic phrase - cite the phrase in reason)
    
    IMPORTANT: For purchase/view counts, the test is TIMEFRAME, not size. A count that implies
    live or recent activity ("in the last hour", "right now", "viewing", "selling fast") is
    social_proof = 1. A static cumulative total with no timeframe ("400K+ sold", "7 bought this",
    "19 sold") is 0. Star ratings and review counts alone are 0.
    
    ELEMENTS:
    {numbered}
    """

    response_schema={
        "type": "array",
        'items':{
            'type': 'object',
            'properties': {
                'index':{'type': 'integer'},
                'label':{'type': 'integer'},
                'category':{'type': 'string'},
                'reason':{'type': 'string'}
            },
            'required':['index','label','category','reason']
        }
    }

    response = client.models.generate_content(
        model = model,
        contents = contents,
        config=genai.types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=response_schema
        )
    )

    labels = json.loads(response.text)
    return labels

def insert_rows(rows_to_insert):
    with psycopg.connect(os.getenv('DATABASE_URL')) as conn:
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                UPDATE elements
                SET 
                    llm_label = %s,
                    llm_category = %s,
                    llm_reason = %s
                WHERE id = %s;
                """, rows_to_insert
            )


def main(n, model='gemini-3.5-flash-lite', only_unlabeled=True):
    data = fetch_elements(only_unlabeled=only_unlabeled)
    text_to_ids = {}
    for id_, text in data:
        text_to_ids.setdefault(text, []).append(id_)
    unique_texts = list(text_to_ids.keys())

    total_chunks = (len(unique_texts) + n - 1) // n
    logger.info('Run start: %s rows, %s unique texts, %s chunks',
                len(data), len(unique_texts), total_chunks)

    failed = []
    for i in range(0, len(unique_texts), n):
        chunk = unique_texts[i:i + n]
        result = None

        for attempt in (1, 2):                          # one automatic retry
            if i > 0 or attempt > 1:
                time.sleep(5)
            try:
                candidate = llm_labeler(chunk, model=model)
            except Exception:
                logger.exception('Chunk %s attempt %s: LLM call failed', i, attempt)
                continue

            returned = sorted(e['index'] for e in candidate)
            if returned == list(range(len(chunk))):
                result = candidate
                break
            logger.warning('Chunk %s attempt %s: bad indices - got %s of %s',
                           i, attempt, len(candidate), len(chunk))

        if result is None:
            logger.error('Chunk %s: FAILED after retries', i)
            failed.append(i)
            continue

        rows = []
        for element in result:
            text = chunk[element['index']]
            for id_ in text_to_ids[text]:
                rows.append((element['label'], element['category'], element['reason'], id_))

        try:
            insert_rows(rows)
            positives = sum(e['label'] for e in result)
            logger.info('Chunk %s: %s texts, %s rows, %s positives',
                        i, len(chunk), len(rows), positives)
        except Exception:
            logger.exception('Chunk %s: DB write failed', i)
            failed.append(i)

    logger.info('Run complete: %s of %s chunks failed: %s', len(failed), total_chunks, failed)
    return failed

if __name__ == '__main__':
    main(20)