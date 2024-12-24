import spacy
import csv
import argparse

# Load the German spaCy model
nlp = spacy.load("de_core_news_lg")

def get_verb_with_particle(token):
    """
    Check if a verb token has a separable prefix and combine them
    Returns the combined form for separable verbs or just the lemma for regular verbs
    """
    if token.pos_ == "VERB":
        for particle in token.rights:
            if particle.dep_ == "svp":  # svp = separable verb prefix
                return f"{particle.text}{token.lemma_}"
    return token.lemma_

def process_text(input_text, output_file):
    # Process the text using spaCy
    doc = nlp(input_text)

    # Extract unique lemmatized tokens with special handling for separable verbs
    unique_lemmatized_tokens = set()
    for token in doc:
        if token.is_alpha:
            if token.pos_ == "VERB":
                verb_form = get_verb_with_particle(token)
                unique_lemmatized_tokens.add(verb_form)
            elif token.dep_ != "svp":  # Skip separated particles as they're handled with their verbs
                unique_lemmatized_tokens.add(token.lemma_)

    # Create a lemma index from the reference CSV
    lemma_index = {}
    with open("U:\\voothi\\20241223170748-token-extraction\\de-news-priority.csv", "r", newline='', encoding='utf-8') as csvfile:
        for line_number, row in enumerate(csv.reader(csvfile)):
            if row:  # Skip empty rows
                word = row[0]
                lemma_index.setdefault(word, line_number)

    # Divide tokens into two groups: found in reference and not found
    found_tokens = [token for token in unique_lemmatized_tokens if token in lemma_index]
    not_found_tokens = [token for token in unique_lemmatized_tokens if token not in lemma_index]

    # Sort tokens: found tokens by their reference index, not found tokens alphabetically
    sorted_found_tokens = sorted(found_tokens, key=lambda token: lemma_index[token])
    sorted_not_found_tokens = sorted(not_found_tokens)

    # Combine both lists: found tokens first, then not found tokens
    final_sorted_tokens = sorted_found_tokens + sorted_not_found_tokens

    # Write the results to CSV if output file is specified
    if output_file:
        with open(output_file, "w", newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerows([[token] for token in final_sorted_tokens])

    # Print each token
    for token in final_sorted_tokens:
        print(token)

if __name__ == "__main__":
    # Create argument parser
    parser = argparse.ArgumentParser(description="Extract and process tokens from German text.")
    
    # Add arguments
    parser.add_argument('--text', type=str, required=True,
                        help='Input text to process')
    parser.add_argument('--output', type=str, required=False,
                        help='Output file path for saving results')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Process the text
    process_text(args.text, args.output)