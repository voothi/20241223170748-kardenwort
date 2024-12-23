import spacy
import csv

# Load the spaCy model
nlp = spacy.load("en_core_web_lg")

# Input text for token extraction
input_text = """Whatever you do, do not ask an AI to summarize the tips we're about to go through. 
Because make no mistake, if you can't summarize information yourself and practice the summarization 
of information, you're not going to be learning on your own. It's just that simple."""

# Process the text
doc = nlp(input_text)

# Extract unique lemmatized tokens
unique_lemmatized_tokens = {token.lemma_ for token in doc if token.is_alpha}

# Create a lemma index from the CSV
lemma_index = {}
with open("en-wiki-priority.csv", "r", newline='', encoding='utf-8') as csvfile:
    for line_number, row in enumerate(csv.reader(csvfile)):
        if row:
            word = row[0]
            lemma_index.setdefault(word, line_number)

# Sort the unique tokens based on their indices in lemma_index
sorted_unique_tokens = sorted(unique_lemmatized_tokens, key=lambda token: lemma_index.get(token, float('inf')))

# Write sorted tokens to CSV
with open("tokens_spacy.csv", "w", newline='', encoding='utf-8') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerows([[token] for token in sorted_unique_tokens])

print("CSV file 'tokens_spacy.csv' created successfully with unique tokens sorted by their order in en-wiki-priority.csv.")