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

# Split the tokens into those found in the index and those not found
found_tokens = [token for token in unique_lemmatized_tokens if token in lemma_index]
not_found_tokens = [token for token in unique_lemmatized_tokens if token not in lemma_index]

# Sort the found tokens by their indices in lemma_index
sorted_found_tokens = sorted(found_tokens, key=lambda token: lemma_index[token])

# Sort the not found tokens alphabetically
sorted_not_found_tokens = sorted(not_found_tokens)

# Combine the lists
final_sorted_tokens = sorted_found_tokens + sorted_not_found_tokens

# Write sorted tokens to CSV
with open("tokens_spacy.csv", "w", newline='', encoding='utf-8') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerows([[token] for token in final_sorted_tokens])

print("CSV file 'tokens_spacy.csv' created successfully with unique tokens sorted, placing not found tokens at the end alphabetically.")