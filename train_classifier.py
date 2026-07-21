import pandas as pd
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, DistilBertForSequenceClassification
import torch
from torch import nn
from torch.optim import AdamW

DATASET_PATH = 'data/ec-darkpattern/dataset.tsv'
MODEL_NAME = 'distilbert-base-uncased'
MAX_LENGTH = 80
BATCH_SIZE = 32
LEARNING_RATE = 2e-5
EPOCHS = 4
SEED = 42
FRAC_LIST = [0.8, 0.1]
SAVE_DIR = 'models/darkpattern-distilbert'


def split_pile(pile, frac_list):
    n_split_pile = round(len(pile))
    n_train, n_validation = round(n_split_pile * frac_list[0]), round(n_split_pile * (frac_list[0] + frac_list[1]))
    train_pile, validation_pile, test_pile = pile.iloc[:n_train], pile.iloc[n_train:n_validation], pile.iloc[
        n_validation:]
    return train_pile, validation_pile, test_pile


def shuffle_split_binary(df, label_column, random_state, frac_list):
    true_label = df.loc[df[label_column] == 1]
    false_label = df.loc[df[label_column] == 0]

    true_label = true_label.sample(frac=1, random_state=random_state)
    false_label = false_label.sample(frac=1, random_state=random_state)

    train_true_label, validation_true_label, test_true_label = split_pile(true_label, frac_list)
    train_false_label, validation_false_label, test_false_label = split_pile(false_label, frac_list)

    train_set = pd.concat([train_true_label, train_false_label])
    validation_set = pd.concat([validation_true_label, validation_false_label])
    test_set = pd.concat([test_true_label, test_false_label])
    return train_set, validation_set, test_set


class DarkPatternDataset(Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {k: v[idx] for k, v in self.encodings.items()}
        item['labels'] = self.labels[idx]
        return item


def build_dataset(dataset, tokenizer, max_length):
    text = list(dataset['text'])
    encoded = tokenizer(
        text,
        truncation=True,
        max_length=max_length,
        return_tensors='pt',
        return_token_type_ids=False,
        padding='max_length'
    )
    labels = torch.tensor(dataset['label'].values)
    return DarkPatternDataset(encodings=encoded, labels=labels)


def train_one_epoch(model, optimizer, loader, criterion):
    model.train()
    total = 0
    for batch in loader:
        optimizer.zero_grad()
        outputs = model(**batch)
        loss = criterion(outputs.logits, batch['labels'])
        loss.backward()
        optimizer.step()
        total += loss.item()
    return total / len(loader)


def evaluate(model, loader, criterion):
    model.eval()
    total = 0
    correct = 0
    val_total = 0
    with torch.no_grad():
        for batch in loader:
            outputs = model(**batch)
            loss = criterion(outputs.logits, batch['labels'])
            preds = torch.argmax(outputs.logits, dim=1)
            correct += (preds == batch['labels']).sum().item()
            total += batch['labels'].size(0)
            val_total += loss.item()
    avg_loss = val_total / len(loader)
    avg_acc = correct / total
    return avg_loss, avg_acc


def main():
    dataset = pd.read_csv(DATASET_PATH, sep='\t', usecols=['text', 'label'])
    train_set, validation_set, test_set = shuffle_split_binary(df=dataset, random_state=SEED, label_column='label',
                                                               frac_list=FRAC_LIST)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    train_dataset, validation_dataset, test_dataset = build_dataset(train_set, tokenizer,
                                                                    max_length=MAX_LENGTH), build_dataset(
        validation_set, tokenizer, max_length=MAX_LENGTH), build_dataset(test_set, tokenizer, max_length=MAX_LENGTH)

    train_loader, validation_loader, test_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE,
                                                              shuffle=True), DataLoader(validation_dataset,
                                                                                        batch_size=BATCH_SIZE), DataLoader(
        test_dataset, batch_size=BATCH_SIZE)

    model = DistilBertForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)
    criterion = nn.CrossEntropyLoss()
    optimizer = AdamW(model.parameters(), lr=LEARNING_RATE)

    best_val_loss = float('inf')
    epoch_values = []
    for epoch in range(EPOCHS):
        train_loss = train_one_epoch(model, optimizer, train_loader,criterion)
        val_loss, val_acc = evaluate(model, validation_loader, criterion)

        print(f'epoch {epoch}: train {train_loss:.4f} | val {val_loss:.4f}')
        epoch_values.append({
            'epoch': epoch,
            'train_loss': train_loss,
            'val_loss': val_loss,
            'val_acc': val_acc
        })

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            model.save_pretrained(SAVE_DIR)
            tokenizer.save_pretrained(SAVE_DIR)
            print(f'new best (val {val_loss:.4f}) - saved')

    test_loss, test_acc = evaluate(model, test_loader, criterion)
    print(f'test {test_loss:.4f} | test {test_acc:.4f}')


if __name__ == '__main__':
    main()
