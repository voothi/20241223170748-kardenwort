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

# Calculate frequency of each token
token_frequency = {}
for token in lemmatized_tokens:
    token_frequency[token] = token_frequency.get(token, 0) + 1

# Read the Morph-Lemma column from the external dictionary
priority_tokens = set()
with open("en-wiki-priority.csv", "r", newline='', encoding='utf-8') as csvfile:
    csv_reader = csv.reader(csvfile)
    next(csv_reader)  # Skip the header
    for row in csv_reader:
        priority_tokens.add(row[0].lower())  # Add the Morph-Lemma to the set

# Sort tokens by frequency (in descending order)
sorted_tokens_by_frequency = sorted(token_frequency.items(), key=lambda item: item[1], reverse=True)

# Separate tokens into priority and non-priority
priority_tokens_list = []
non_priority_tokens_list = []

for token, frequency in sorted_tokens_by_frequency:
    if token in priority_tokens:
        priority_tokens_list.append((token, frequency))
    else:
        non_priority_tokens_list.append((token, frequency))

# Sort non-priority tokens alphabetically
non_priority_tokens_list.sort(key=lambda item: item[0])

# Combine both lists
combined_tokens = priority_tokens_list + non_priority_tokens_list

# Write data to a CSV file
with open("filtered_tokens_spacy.csv", "w", newline='', encoding='utf-8') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow(["Token", "Frequency"])  # Write header
    for token, frequency in combined_tokens:
        csv_writer.writerow([token, frequency])

print("CSV file 'filtered_tokens_spacy.csv' created successfully.")