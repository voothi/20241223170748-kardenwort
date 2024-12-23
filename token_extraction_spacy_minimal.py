import spacy
import csv

nlp = spacy.load("en_core_web_lg")

input_text = """Whatever you do, do not ask an AI to summarize the tips we're about to go through. 
Because make no mistake, if you can't summarize information yourself and practice the summarization 
of information, you're not going to be learning on your own. It's just that simple."""

doc = nlp(input_text)

unique_lemmatized_tokens = set(token.lemma_ for token in doc if token.is_alpha)

lemma_index = {}
with open("en-wiki-priority.csv", "r", newline='', encoding='utf-8') as csvfile:
    for line_number, row in enumerate(csv.reader(csvfile)):
        if row:
            word = row[0]
            if word not in lemma_index or line_number < lemma_index[word]:
                lemma_index[word] = line_number

sorted_unique_tokens = sorted(unique_lemmatized_tokens, 
                            key=lambda token: lemma_index.get(token, float('inf')))

with open("tokens_spacy.csv", "w", newline='', encoding='utf-8') as csvfile:
    csv_writer = csv.writer(csvfile)
    for token in sorted_unique_tokens:
        csv_writer.writerow([token])

print("CSV file 'tokens_spacy.csv' created successfully with unique tokens sorted by their order in en-news-2023-1m-words.csv.")