import re
import sys
import os

def clean_german_frequency_list():
    input_file = "data/de/deu-mixed-typical-2011-1m-words copy.csv"
    output_file = "data/de/deu-mixed-typical-2011-1m-words.csv"
    
    if not os.path.exists(input_file):
        print(f"Error: Backup file {input_file} not found. Please make sure the backup file exists.")
        sys.exit(1)
        
    print(f"Cleaning {input_file} -> {output_file}...")
    
    # Regex to match valid German words (including hyphens and abbreviations like Dr. or z.B.)
    # Must start with a letter, end with a letter or dot, and contain only letters, dots, or hyphens in between.
    valid_word_pat = re.compile(r'^[a-zA-ZäöüÄÖÜß][a-zA-ZäöüÄÖÜß.-]*[a-zA-ZäöüÄÖÜß.]$')
    
    cleaned_words = []
    seen = set()
    
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            word = line.strip()
            if not word:
                continue
                
            # Strip leading/trailing ellipsis or standard punctuation
            # (Leipzig often includes words with surrounding punctuation)
            cleaned_word = word.strip('….,;:!?\'"`()[]{}')
            
            if not cleaned_word:
                continue
                
            # Check regex
            if valid_word_pat.match(cleaned_word):
                if cleaned_word not in seen:
                    seen.add(cleaned_word)
                    cleaned_words.append(cleaned_word)
                    
    # Write output
    with open(output_file, "w", encoding="utf-8", newline="\n") as f:
        for w in cleaned_words:
            f.write(w + "\n")
            
    print(f"Done! Cleaned size: {len(cleaned_words)}")
    print(f"Saved optimized list to {output_file}")

if __name__ == "__main__":
    clean_german_frequency_list()
