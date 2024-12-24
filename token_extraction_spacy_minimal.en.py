import spacy
import csv
import argparse

# Load the spaCy model
nlp = spacy.load("en_core_web_lg")

def process_text(input_text, output_file, sentence_context_size, detailed_output):
    # Process the text
    doc = nlp(input_text)

    # Extract unique lemmatized tokens
    unique_lemmatized_tokens = {token.lemma_ for token in doc if token.is_alpha}

    # Extract sentences
    sentences = list(doc.sents)

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

    # Dictionary to map tokens to their sentences
    token_to_sentence = {}

    for sent_index, sent in enumerate(sentences):
        for token in sent:
            if token.is_alpha:
                token_to_sentence[token.lemma_] = (sent_index, sent.text)

    # Write sorted tokens to TSV if output file is specified
    if output_file:
        with open(output_file, "w", newline='', encoding='utf-8') as tsvfile:
            tsv_writer = csv.writer(tsvfile, delimiter='\t')
            for token in final_sorted_tokens:
                sent_index, sentence = token_to_sentence[token]
                # Get context sentences
                start_index = max(0, sent_index - sentence_context_size)
                end_index = min(len(sentences), sent_index + sentence_context_size + 1)
                left_context = ' '.join(sent.text for sent in sentences[start_index:sent_index])
                right_context = ' '.join(sent.text for sent in sentences[sent_index + 1:end_index])
                # Write the row
                tsv_writer.writerow([token, sentence, left_context, right_context])

    # Print each token
    for token in final_sorted_tokens:
        print(token)
    print()  # Empty line to separate the list of tokens from the detailed output

    # Print each token with its sentence and context if detailed output is requested
    if detailed_output:
        for token in final_sorted_tokens:
            sent_index, sentence = token_to_sentence[token]
            # Get context sentences
            start_index = max(0, sent_index - sentence_context_size)
            end_index = min(len(sentences), sent_index + sentence_context_size + 1)
            left_context = ' '.join(sent.text for sent in sentences[start_index:sent_index])
            right_context = ' '.join(sent.text for sent in sentences[sent_index + 1:end_index])
            
            # Print the formatted output
            print(token)
            if left_context:
                print(left_context)
            print(sentence)
            if right_context:
                print(right_context)
            print()  # Empty line between entries

if __name__ == "__main__":
    # Create argument parser
    parser = argparse.ArgumentParser(description="Extract and process tokens from English text.")

    # Add arguments
    parser.add_argument('--text', type=str, required=True,
                        help='Input text to process')
    parser.add_argument('--output', type=str, required=False, default=None,
                        help='Output file path for saving results')
    parser.add_argument('--sentence_context_size', type=int, default=1,
                        help='Number of sentences to include before and after the target sentence (default: 1)')
    parser.add_argument('--detailed', action='store_true',
                        help='Enable detailed output in console with sentence and context')
    
    # Parse arguments
    args = parser.parse_args()

    # Process the text
    process_text(args.text, args.output, args.sentence_context_size, args.detailed)