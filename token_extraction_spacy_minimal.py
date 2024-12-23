import spacy
import csv

# Load the English NLP model
nlp = spacy.load("en_core_web_lg")

# Define the input text
input_text = """Whatever you do, do not ask an AI to summarize the tips we're about to go through. 
Because make no mistake, if you can't summarize information yourself and practice the summarization 
of information, you're not going to be learning on your own. It's just that simple."""

# Process the text with spaCy
doc = nlp(input_text)

# Lemmatize tokens and filter out non-alphabetic tokens, then convert to a set to remove duplicates
unique_lemmatized_tokens = set(token.lemma_ for token in doc if token.is_alpha)

# Convert the set back to a list and sort it alphabetically
sorted_unique_tokens = sorted(unique_lemmatized_tokens)

# Write data to a CSV file in alphabetical order
with open("tokens_spacy.csv", "w", newline='', encoding='utf-8') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow(["Token"])  # Write header
    for token in sorted_unique_tokens:
        csv_writer.writerow([token])

print("CSV file 'tokens_spacy.csv' created successfully with unique tokens in alphabetical order.")