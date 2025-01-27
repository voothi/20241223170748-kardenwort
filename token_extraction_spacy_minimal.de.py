import spacy
import csv
import argparse

# Load the German spaCy model
nlp = spacy.load("de_core_news_lg")

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

def get_original_form_with_particle(token):
    if token.pos_ == "VERB":
        particle = next((child for child in token.children if child.dep_ == "svp"), None)
        if particle:
            return f"{token.text} {particle.text}"
    return token.text

def process_text(input_text, output_file, sentence_context_size, detailed_output, include_simple_list, lemma_index_file):
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
                    verb_form = get_verb_with_particle(token)
                    unique_lemmatized_tokens.add(verb_form)
                    token_to_sentence[verb_form] = (sent_index, sent.text)
                    token_to_original_form[verb_form] = get_original_form_with_particle(token)  # Используем новую функцию
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
                sentence_tokens_set = {get_verb_with_particle(token) if token.pos_ == "VERB" else token.lemma_ 
                                       for token in sent_doc if token.is_alpha and token.dep_ != "svp"}

                # Sort sentence tokens according to lemma_index
                sentence_tokens_sorted = sorted(sentence_tokens_set, key=lambda x: lemma_index.get(x, float('inf')))

                simple_list_entry = '\n'.join(sentence_tokens_sorted) if include_simple_list else ''

                # Write the row
                original_form = token_to_original_form[token]
                tsv_writer.writerow([token, original_form, simple_list_entry, left_context, sentence, right_context])

    # Print the simple list of tokens, each on a new line
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
    parser = argparse.ArgumentParser(description="Extract and process tokens from German text.")
    
    # Add arguments
    parser.add_argument('--text', type=str, required=True,
                        help='Input text to process')
    parser.add_argument('--output', type=str, required=False,
                        help='Output TSV file path for saving results')
    parser.add_argument('--sentence-context-size', type=int, default=1,
                        help='Number of sentences to include before and after the target sentence (default: 1)')
    parser.add_argument('--detailed', action='store_true',
                        help='Enable detailed output in console with sentence and context')
    parser.add_argument('--include-simple-list', action='store_true',
                        help='Include a simple list of tokens in the last column of the output file')
    # parser.add_argument('--lemma-index-file', type=str, default="U:\\voothi\\20241224175657\\20241223170748-token-extraction\\de-news-priority.csv",
    parser.add_argument('--lemma-index-file', type=str, default="U:\\voothi\\20241224175657\\20241223170748-token-extraction\\deu-mixed-typical-2011-1m-words.csv",
                        help='Path to the lemma index CSV file')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Process the text
    process_text(args.text, args.output, args.sentence_context_size, args.detailed, args.include_simple_list, args.lemma_index_file)