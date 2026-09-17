from transformers import AutoTokenizer, DistilBertForSequenceClassification
import torch

INPUT_FOLDER ='models/darkpattern-distilbert'
_tokenizer=None
_model=None

def load_tok_and_model(input_folder):
    global _tokenizer,_model
    if _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained(input_folder)
        _model = DistilBertForSequenceClassification.from_pretrained(input_folder)
        _model.eval()
    return _tokenizer,_model

def predict(text):
    tokenizer,model = load_tok_and_model(INPUT_FOLDER)
    encoded = tokenizer(text,
                        truncation=True,
                        padding='max_length',
                        max_length=80,
                        return_tensors='pt',
                        return_token_type_ids=False)

    with torch.no_grad():
        outputs = model(**encoded)
        probs = torch.softmax(outputs.logits,dim=1)
        prediction = torch.argmax(probs,dim=1).item()
        confidence = probs[0][prediction].item()
        return prediction,confidence