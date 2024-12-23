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
unique_lemmatized_tokens = set(token.lemma_.lower() for token in doc if token.is_alpha)

# Read the priority CSV file and create a dictionary for lemma indices
lemma_index = {}
with open("en-news-2023-1m-words.csv", "r", newline='', encoding='utf-8') as csvfile:
    # Используем enumerate для отслеживания номера строки (начиная с 0)
    for line_number, row in enumerate(csv.reader(csvfile)):
        if row:  # Проверяем, что строка не пустая
            word = row[0]  # Получаем слово и нормализуем его
            # Сохраняем минимальный индекс для каждого слова
            if word not in lemma_index or line_number < lemma_index[word]:
                lemma_index[word] = line_number

# Sort unique tokens based on their index in the priority CSV file
# Используем float('inf') для слов, которых нет в словаре индексов
sorted_unique_tokens = sorted(unique_lemmatized_tokens, 
                            key=lambda token: lemma_index.get(token, float('inf')))

# Write data to a CSV file in priority order based on CSV file line number
with open("tokens_spacy.csv", "w", newline='', encoding='utf-8') as csvfile:
    csv_writer = csv.writer(csvfile)
    for token in sorted_unique_tokens:
        csv_writer.writerow([token])

print("CSV file 'tokens_spacy.csv' created successfully with unique tokens sorted by their order in en-news-2023-1m-words.csv.")