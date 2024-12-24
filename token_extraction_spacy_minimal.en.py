import spacy
import csv
import argparse

# Load the spaCy model
nlp = spacy.load("en_core_web_lg")

def process_text(input_text, output_file):
    # Process the text
    doc = nlp(input_text)

    # Extract unique lemmatized tokens
    unique_lemmatized_tokens = {token.lemma_ for token in doc if token.is_alpha}

    # Create a lemma index from the CSV
    lemma_index = {}
    with open("U:\\voothi\\20241223170748-token-extraction\\en-wiki-priority.csv", "r", newline='', encoding='utf-8') as csvfile:
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

    # Write sorted tokens to CSV if output file is specified
    if output_file:
        with open(output_file, "w", newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerows([[token] for token in final_sorted_tokens])
        # print(f"CSV file '{output_file}' created successfully with unique tokens sorted, placing not found tokens at the end alphabetically.")

    # Print each token
    for token in final_sorted_tokens:
        print(token)

if __name__ == "__main__":
    # Create argument parser
    parser = argparse.ArgumentParser(description="Extract and process tokens from English text.")

    # Add arguments
    parser.add_argument('--text', type=str, required=True,
                        help='Input text to process')
    parser.add_argument('--output', type=str, required=False, default=None,
                        help='Output file path for saving results')

    # Parse arguments
    args = parser.parse_args()

    # Process the text
    process_text(args.text, args.output)