import spacy
import csv
import argparse
from datetime import datetime

def get_verb_with_particle(token):
    """
    Check if a verb token has a separable prefix and combine them.
    Returns the combined form for separable verbs or just the lemma for regular verbs.
    """
    if token.pos_ == "VERB":
        for particle in token.rights:
            if particle.dep_ == "svp":  # svp = separable verb prefix
                return f"{particle.text}{token.lemma_}"
    return token.lemma_

def get_original_form_with_particle(token):
    if token.pos_ == "VERB":
        particle = next((child for child in token.children if child.dep_ == "svp"), None)
        if particle:
            return f"{token.text} {particle.text}"
    return token.text

def load_lemma_index(file_path):
    lemma_index = {}
    try:
        with open(file_path, "r", newline='', encoding='utf-8') as csvfile:
            csv_reader = csv.reader(csvfile)
            for line_number, row in enumerate(csv_reader):
                if row:  # Skip empty rows
                    word = row[0]
                    if word not in lemma_index:  # Add only if the lemma is not yet in the dictionary
                        lemma_index[word] = line_number
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return {}
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return {}
    return lemma_index

def process_text(input_text, output_file, sentence_context_size, detailed_output, include_simple_list, lemma_index_file, two_column_output, html_output, timestamp, original_form_in_simple_list, two_column_output_to_file, language):
    # Load the lemma index
    lemma_index = load_lemma_index(lemma_index_file)

    # Process the text using spaCy
    doc = nlp(input_text)

    # Extract unique lemmatized tokens with special handling for separable verbs
    unique_lemmatized_tokens = set()
    token_to_sentence = {}
    token_to_original_form = {}

    # Extract sentences
    sentences = list(doc.sents)

    for sent_index, sent in enumerate(sentences):
        for token in sent:
            if token.is_alpha:
                if token.pos_ == "VERB":
                    if language == "de":
                        verb_form = get_verb_with_particle(token)
                    else:
                        verb_form = token.lemma_
                    unique_lemmatized_tokens.add(verb_form)
                    token_to_sentence[verb_form] = (sent_index, sent.text)
                    if language == "de":
                        token_to_original_form[verb_form] = get_original_form_with_particle(token)
                    else:
                        token_to_original_form[verb_form] = token.text
                elif token.dep_ != "svp":  # Skip separated particles as they're handled with their verbs
                    unique_lemmatized_tokens.add(token.lemma_)
                    token_to_sentence[token.lemma_] = (sent_index, sent.text)
                    token_to_original_form[token.lemma_] = token.text

    # Divide tokens into two groups: found in reference and not found
    found_tokens = [token for token in unique_lemmatized_tokens if token in lemma_index]
    not_found_tokens = [token for token in unique_lemmatized_tokens if token not in lemma_index]

    # Sort tokens: found tokens by their reference index, not found tokens alphabetically
    sorted_found_tokens = sorted(found_tokens, key=lambda token: lemma_index[token])
    sorted_not_found_tokens = sorted(not_found_tokens)

    # Combine both lists: found tokens first, then not found tokens
    final_sorted_tokens = sorted_found_tokens + sorted_not_found_tokens

    # Write the results to TSV if output file is specified
    if output_file:
        if timestamp:
            # Extract the directory and filename from the output path
            import os
            output_dir = os.path.dirname(output_file)
            output_filename = os.path.basename(output_file)
            # Prepend timestamp to the filename
            timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
            new_output_filename = f"{timestamp_str}-{output_filename}"
            output_file = os.path.join(output_dir, new_output_filename)

        with open(output_file, "w", newline='', encoding='utf-8') as tsvfile:
            tsv_writer = csv.writer(tsvfile, delimiter='\t')
            for token in final_sorted_tokens:
                sent_index, sentence = token_to_sentence[token]
                # Get context sentences
                start_index = max(0, sent_index - sentence_context_size)
                end_index = min(len(sentences), sent_index + sentence_context_size + 1)
                left_context = ' '.join(sent.text for sent in sentences[start_index:sent_index])
                right_context = ' '.join(sent.text for sent in sentences[sent_index + 1:end_index])

                # Extract tokens from the sentence and create a simple set to ensure uniqueness
                sent_doc = nlp(sentence)
                sentence_tokens_set = {get_verb_with_particle(token) if token.pos_ == "VERB" and language == "de" else token.lemma_ 
                                       for token in sent_doc if token.is_alpha and token.dep_ != "svp"}

                # Sort sentence tokens according to lemma_index
                sentence_tokens_sorted = sorted(sentence_tokens_set, key=lambda x: lemma_index.get(x, float('inf')))

                # Create simple list entry with both lemma and original form
                if original_form_in_simple_list:
                    simple_list_entry = '\n'.join(f"{sentence_token}\t{token_to_original_form[sentence_token]}" for sentence_token in sentence_tokens_sorted) if include_simple_list else ''
                else:
                    simple_list_entry = '\n'.join(sentence_tokens_sorted) if include_simple_list else ''

                # Write the row
                original_form = token_to_original_form[token]
                if language == "de":
                    if two_column_output_to_file:
                        tsv_writer.writerow([token, token, original_form, "", "", left_context, sentence, right_context, "", "", "", simple_list_entry, sentence, "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "1", "", "", "", "", "", "", "1"])
                    else:
                        tsv_writer.writerow([token, token,            "", "", "", left_context, sentence, right_context, "", "", "", simple_list_entry, sentence, "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "1", "", "", "", "", "", "", "1"])

                if language == "en":
                    if two_column_output_to_file:
                        tsv_writer.writerow([token, token, original_form, "", "", left_context, sentence, right_context, "", "", "", simple_list_entry, sentence, "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "1", "", "", "", "", "", "", "", "1"])
                    else:
                        tsv_writer.writerow([token, token,            "", "", "", left_context, sentence, right_context, "", "", "", simple_list_entry, sentence, "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "1", "", "", "", "", "", "", "", "1"])


    # Output tokens in HTML table if html_output is enabled
    if html_output:
        print("<table>")
        for token in final_sorted_tokens:
            original_form = token_to_original_form[token]
            print(f"<tr><td>{token}</td><td>{original_form}</td></tr>")
        print("</table>")
    # Output tokens in two columns if two_column_output is enabled
    elif two_column_output:
        for token in final_sorted_tokens:
            original_form = token_to_original_form[token]
            print(f"{token}\t{original_form}")
    else:
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

def read_input_text(input_file):
    try:
        with open(input_file, "r", encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        print(f"File not found: {input_file}")
        exit(1)
    except Exception as e:
        print(f"Error reading file {input_file}: {e}")
        exit(1)

if __name__ == "__main__":
    # Create argument parser
    parser = argparse.ArgumentParser(description="Extract and process tokens from text.")
    
    # Add arguments
    parser.add_argument('--language', type=str, default='de', choices=['de', 'en'],
                        help='Language for processing (default: de)')
    parser.add_argument('--lemma-index-file', type=str, default="",
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
    
    # Determine the lemma index file based on the language
    if not args.lemma_index_file:
        if args.language == 'de':
            args.lemma_index_file = "U:\\voothi\\20241223170748-token-extraction\\deu-mixed-typical-2011-1m-words.csv"
        else:
            # args.lemma_index_file = "U:\\voothi\\20241223170748-token-extraction\\en-news-2023-1m-words.csv"
            args.lemma_index_file = "U:\\voothi\\20241223170748-token-extraction\\en-wiki-priority.csv"
    
    # Determine input text
    if args.input and args.text:
        print("Error: Both --input and --text cannot be specified simultaneously.")
        exit(1)
    elif args.input:
        input_text = read_input_text(args.input)
    elif args.text:
        input_text = args.text
    else:
        print("Error: Either --input or --text must be specified.")
        exit(1)
    
    # Load the appropriate spaCy model based on the language
    global nlp
    if args.language == 'de':
        nlp = spacy.load("de_core_news_lg")
    else:
        nlp = spacy.load("en_core_web_lg")
    
    # Process the text
    process_text(input_text, args.output, args.sentence_context_size, args.detailed, args.include_simple_list, args.lemma_index_file, args.two_column_output, args.html, args.timestamp, args.original_form_in_simple_list, args.two_column_output_to_file, args.language)
