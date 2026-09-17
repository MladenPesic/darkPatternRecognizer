import psycopg
import pandas as pd
from dotenv import load_dotenv
import os
from train_classifier import shuffle_split_binary,split_pile
import torch

load_dotenv()

def fetch_labeled_elements():
    query="""
    SELECT id,scan_id,element_text,geometry_x,geometry_y,geometry_width,geometry_height,llm_label
    FROM elements
    WHERE llm_label IS NOT NULL
        AND geometry_width IS NOT NULL
    """

    with psycopg.connect(os.getenv('DATABASE_URL')) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            rows  = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
    return pd.DataFrame(rows,columns=columns)

df = fetch_labeled_elements()
df['x2'] = df['geometry_x']+df['geometry_width']
df['y2'] = df['geometry_y']+df['geometry_height']

grouped = df.groupby('scan_id',as_index=False).agg(
    page_width = ('x2','max'),
    page_height = ('y2','max')
)

merged = df.merge(grouped,on='scan_id')
merged['area'] = merged['geometry_width'] * merged['geometry_height']
merged['aspect_ratio'] = merged['geometry_width'] / merged['geometry_height']
merged['x_norm'] = merged['geometry_x'] / merged['page_width']
merged['y_norm'] = merged['geometry_y'] / merged['page_height']
merged['width_norm'] = merged['geometry_width'] / merged['page_width']
merged['height_norm'] = merged['geometry_height'] / merged['page_height']
merged['area_norm'] = merged['area'] / (merged['page_width'] * merged['page_height'])

merged['text_count'] = merged.groupby(['scan_id','element_text']).transform('size')

train_set,validation_set,test_set = shuffle_split_binary(
    df=merged,
    label_column='llm_label',
    random_state=42,
    frac_list=[0.8,0.1]
)
train_index,validation_index,test_index = set(train_set.index),set(validation_set.index),set(test_set.index)
len(train_index & test_index)
len(train_index & validation_index)
len(validation_index & test_index)
for split_df in [train_set,validation_set,test_set]:
    print(split_df['llm_label'].value_counts(normalize=True))

counts = train_set['llm_label'].value_counts()
total = len(train_set)
class_weights = torch.tensor([
    total/(2*counts[0]),
    total/(2*counts[1])
], dtype=torch.float)