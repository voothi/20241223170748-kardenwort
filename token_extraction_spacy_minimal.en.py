import spacy
import csv
import argparse

# Load the spaCy model
nlp = spacy.load("en_core_web_lg")

def load_lemma_index(lemma_index_file):
    lemma_index = {}
    with open(lemma_index_file, "r", newline='', encoding='utf-8') as csvfile:
        for line_number, row in enumerate(csv.reader(csvfile)):
            if row:
                word = row[0]
                lemma_index.setdefault(word, line_number)
    return lemma_index

def process_text(input_text, lemma_index, output_file, sentence_context_size, detailed_output, two_column_output, html_output, timestamp, two_column_output_to_file, include_simple_list, original_form_in_simple_list):
    # Process the text
    doc = nlp(input_text)

    # Extract unique lemmatized tokens and their original forms
    token_to_original_form = {token.lemma_: token.text for token in doc if token.is_alpha}

    # Extract sentences
    sentences = list(doc.sents)

    # Split the tokens into those found in the index and those not found
    found_tokens = [token for token in token_to_original_form if token in lemma_index]
    not_found_tokens = [token for token in token_to_original_form if token not in lemma_index]

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
        if timestamp:
            import datetime
            timestamp_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            output_file = f"{timestamp_str}_{output_file}"
        with open(output_file, "w", newline='', encoding='utf-8') as tsvfile:
            tsv_writer = csv.writer(tsvfile, delimiter='\t')
            for token in final_sorted_tokens:
                sent_index, sentence = token_to_sentence[token]
                # Get context sentences
                start_index = max(0, sent_index - sentence_context_size)
                end_index = min(len(sentences), sent_index + sentence_context_size + 1)
                left_context = ' '.join(sent.text for sent in sentences[start_index:sent_index])
                right_context = ' '.join(sent.text for sent in sentences[sent_index + 1:end_index])
                # Prepare the row
                row = [token, sentence, left_context, right_context]
                if two_column_output_to_file:
                    row.append(token_to_original_form[token])
                if include_simple_list:
                    simple_list = ' '.join(final_sorted_tokens)
                    if original_form_in_simple_list:
                        simple_list = ' '.join(token_to_original_form[token] for token in final_sorted_tokens)
                    row.append(simple_list)
                # Write the row
                tsv_writer.writerow(row)

    # Print each token
    for token in final_sorted_tokens:
        if two_column_output:
            print(f"{token}\t{token_to_original_form[token]}")
        else:
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
    parser.add_argument('--lemma-index-file', type=str, default="U:\\voothi\\20241223170748-token-extraction\\en-wiki-priority.csv",
                        help='Path to the lemma index CSV file')
    parser.add_argument('--text', type=str,
                        help='Input text to process')
    parser.add_argument('--input', type=str,
                        help='Path to input text file to process')
    parser.add_argument('--detailed', action='store_true',
                        help='STDOUT: Enable detailed output in console with sentence and context')
    parser.add_argument('--two-column-output', action='store_true',
                        help='STDOUT: Output tokens in two columns: token and original form')
    parser.add_argument('--html', action='store_true',
                        help='STDOUT: Output tokens in an HTML table')
    parser.add_argument('--sentence-context-size', type=int, default=1,
                        help='CSV: Number of sentences to include before and after the target sentence (default: 1)')
    parser.add_argument('--output', type=str, required=False,
                        help='CSV: Output TSV file path for saving results')
    parser.add_argument('--timestamp', action='store_true',
                        help='CSV: Prepend timestamp to the output file name')
    parser.add_argument('--two-column-output-to-file', action='store_true',
                        help='CSV: Include original forms in the TSV output file when writing to file')
    parser.add_argument('--include-simple-list', action='store_true',
                        help='CSV: Include a simple list of tokens in the last column of the output file')
    parser.add_argument('--original-form-in-simple-list', action='store_true',
                        help='CSV: Include original forms in the simple list entry in the TSV file')
    
    # Parse arguments
    args = parser.parse_args()

    # Load the lemma index
    lemma_index = load_lemma_index(args.lemma_index_file)

    # Process the text
    process_text(args.text, lemma_index, args.output, args.sentence_context_size, args.detailed, args.two_column_output, args.html, args.timestamp, args.two_column_output_to_file, args.include_simple_list, args.original_form_in_simple_list)
