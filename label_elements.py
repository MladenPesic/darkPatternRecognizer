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

def fetch_elements():
    with psycopg.connect(os.getenv('DATABASE_URL')) as conn:
        with conn.cursor() as cursor:
            text="""
            SELECT id,element_text
            FROM elements
            WHERE element_text IS NOT NULL
              AND TRIM(element_text) <> ''
              AND geometry_width IS NOT NULL
            ORDER BY element_text; 
            """

            cursor.execute(text)
            rows = cursor.fetchall()
            return rows

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
    "Add to cart" -> label 0, category none (neutral UI)
    "Sale Price" -> label 0, category none (static label, no tactic)
    "#1 Bestseller" -> label 0, category none (static descriptive popularity claim)
    "Hurry! These savings end soon" -> label 1, category urgency (manufactured time pressure)
    "127 people are viewing this right now" -> label 1, category social_proof (fabricated real-time pressure)
    "No thanks, I'll pay full price" -> label 1, category confirmshaming
    "CABRRR Straight Fit Men Grey Jeans 69% off (203) Only few left" -> label 1, category scarcity (mostly-benign product listing with an embedded scarcity phrase)
    
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

data = fetch_elements()
text_to_ids = {}
for id_,text in data:
    text_to_ids.setdefault(text, []).append(id_)

unique_texts = list(text_to_ids.keys())


for i in range(0,len(unique_texts),50):
    chunk = unique_texts[i:i+50]

    if i >0:
        time.sleep(5)

    try:
        result = llm_labeler(chunk,model='gemini-3.1-flash-lite')
    except Exception:
        logger.exception('LLM labeler failed')
        #continue

    returned = sorted(e['index'] for e in result)
    if returned != list(range(len(chunk))):
        logger.error('Chunk %s: bad indices - expected 0..%s, got %s results',
                     i, len(chunk) - 1, len(result))
        #continue

    rows=[]
    for element in result:
        text = chunk[element['index']]
        for id_ in text_to_ids[text]:
            rows.append((element['label'],element['category'],element['reason'],id_))
    try:
        insert_rows(rows)
        positives = sum(e['label'] for e in result)
        logger.info('Chunk %s: %s texts, %s rows updated, %s positives',
                    i, len(chunk), len(rows), positives)
    except Exception:
        logger.exception('Chunk %s: DB write failed', i)
