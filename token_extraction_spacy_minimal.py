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

# Lemmatize tokens and filter out non-alphabetic tokens
lemmatized_tokens = [token.lemma_ for token in doc if token.is_alpha]

# Read the Morph-Lemma column from the external dictionary
priority_tokens = set()
with open("en-wiki-priority.csv", "r", newline='', encoding='utf-8') as csvfile:
    csv_reader = csv.reader(csvfile)
    next(csv_reader)  # Skip the header
    for row in csv_reader:
        priority_tokens.add(row[0].lower())  # Add the Morph-Lemma to the set

# Filter lemmatized tokens based on the priority tokens
filtered_tokens = [token for token in lemmatized_tokens if token in priority_tokens]

# Calculate frequency of each token
token_frequency = {}
for token in filtered_tokens:
    token_frequency[token] = token_frequency.get(token, 0) + 1

# Sort tokens by frequency (in descending order)
sorted_tokens = sorted(token_frequency.items(), key=lambda item: item[1], reverse=True)

# Write data to a CSV file
with open("filtered_tokens_spacy.csv", "w", newline='', encoding='utf-8') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow(["Token", "Frequency"])  # Write header
    for token, frequency in sorted_tokens:
        csv_writer.writerow([token, frequency])

print("CSV file 'filtered_tokens_spacy.csv' created successfully.")