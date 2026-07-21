from transformers import AutoTokenizer, DistilBertForSequenceClassification
import torch

INPUT_FOLDER ='models/darkpattern-distilbert'
tokenizer = AutoTokenizer.from_pretrained(INPUT_FOLDER)
model = DistilBertForSequenceClassification.from_pretrained(INPUT_FOLDER)
model.eval()

def predict(text):
    encoded = tokenizer(text,
                        truncation=True,
                        padding='max_length',
                        max_length=80,
                        return_tensors='pt',
                        return_token_type_ids=False)

    with torch.no_grad():
        outputs = model(**encoded)
        probs = torch.softmax(outputs.logits,dim=1)
        pred = torch.argmax(probs,dim=1).item()
        confidence = probs[0][pred].item()
        return pred,confidence