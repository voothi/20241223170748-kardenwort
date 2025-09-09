// Переписать этот код с Python на Golang — это интересная и объемная задача. Самый сложный аспект — это библиотека spaCy, которая является мощным инструментом для обработки естественного языка (NLP) и написана на Python с использованием высокопроизводительных компонентов на Cython и C++. Прямого, эквивалентного по функциональности и производительности, готового решения для spaCy на чистом Go на данный момент не существует.

// Целесообразность и сложности

// Возможность: Технически переписать код на Go возможно.

// Целесообразность:

// Высокая целесообразность для не-NLP частей: Все операции с файлами (чтение CSV, запись TSV), парсинг аргументов командной строки, работа с датами, сортировка данных, управление контекстом предложений — все это отлично и эффективно реализуется на Go. Go известен своей производительностью и простотой в параллельной обработке данных, что может быть преимуществом для больших текстовых файлов.

// Низкая целесообразность для NLP-части (spaCy): Это критический блок.

// Отсутствие прямого аналога: Как упомянуто, прямого Go-эквивалента spaCy с ее обширными предобученными моделями (особенно для немецкого языка с учетом svp — separable verb prefix, что требует сложного синтаксического анализа) нет.

// Альтернативы для NLP в Go:

// Легковесные библиотеки: Существуют Go-библиотеки для базового NLP (токенизация, стемминг, POS-тегирование), например, github.com/jdkato/prose, github.com/neurosnap/sentences, github.com/ikawaha/kagome (для японского). Однако они, как правило, не предоставляют полного синтаксического анализа (dependency parsing), который spaCy использует для определения svp и token.rights/token.children.

// Сторонние сервисы/IPC: Наиболее реалистичные подходы для сохранения функциональности spaCy при переходе на Go:

// Микросервис на Python: Поднять небольшой HTTP-сервер на Python (например, с использованием Flask или FastAPI), который будет принимать текст, обрабатывать его с помощью spaCy и возвращать структурированные данные (JSON). Go-приложение будет обращаться к этому микросервису. Это добавляет накладные расходы на сеть, но позволяет использовать spaCy без изменений.

// Вызов Python как подпроцесса (IPC): Запускать Python-скрипт с spaCy как подпроцесс из Go-приложения, передавать данные через стандартные потоки ввода/вывода (stdin/stdout) и использовать JSON для обмена данными. Это более тесная интеграция, но также требует обработки JSON и управления подпроцессом.

// Gorgonia/Go-NLP: Есть попытки создания глубокообучающих фреймворков на Go (например, Gorgonia), но создание и обучение моделей, аналогичных spaCy, с нуля — это огромный объем работы, нецелесообразный для простого "переписывания".

// Вывод: Если ключевой функциональностью является NLP (лемматизация, особенно с svp), то "переписать" в чистом Go будет крайне сложно без существенного снижения качества или огромных усилий по разработке собственного NLP-движка. Наиболее прагматичный подход — перенести всю логику на Go, а для NLP-части использовать spaCy через микросервис или подпроцесс.

// Используемые библиотеки в Golang

// Для переписанного кода на Go я буду использовать следующие стандартные и сторонние (но широко используемые) библиотеки:

// Стандартные библиотеки:

// fmt: Для форматированного ввода/вывода (аналог print()).

// os: Для работы с файлами, директориями, выхода из программы (аналог os, sys.exit).

// path/filepath: Для работы с путями к файлам (аналог os.path).

// bufio: Для эффективного построчного чтения файлов.

// encoding/csv: Для чтения и записи CSV/TSV файлов (аналог csv).

// time: Для работы с датами и временем (аналог datetime).

// strings: Для операций со строками.

// sort: Для сортировки слайсов.

// flag: Для парсинга аргументов командной строки (аналог argparse).

// Сторонние библиотеки (для NLP - объяснение):

// В этом примере я не буду использовать сторонние NLP-библиотеки на Go, поскольку ни одна из них не предоставляет функциональность spaCy (особенно dependency parsing с svp для немецкого) "из коробки". Вместо этого, я симулирую интерфейс spaCy и добавлю комментарии, объясняющие, как это должно быть реализовано с внешним вызовом Python/spaCy.

// Если бы мы реализовывали через IPC, понадобилась бы encoding/json для обмена данными с Python.

// Переписанный код на Golang (с симуляцией NLP)

// Я создам упрощенные структуры Doc и Token, чтобы имитировать то, что возвращает spaCy, и заглушку для nlp объекта, которая будет просто возвращать фиктивные данные. В реальном приложении эта заглушка была бы заменена вызовами Python-сервиса.

package main

import (
	"bufio"
	"encoding/csv"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"flag" // Для парсинга аргументов командной строки
)

// --- Симуляция spaCy NLP в Go ---
// В реальном приложении эти структуры и методы были бы результатом обработки данных,
// полученных от внешнего spaCy-сервиса (например, через JSON по HTTP или IPC).

// Token имитирует spaCy.Token
type Token struct {
	Text     string
	Lemma    string
	POS      string // Part-of-Speech, e.g., "VERB", "NOUN"
	Dep      string // Dependency relation, e.g., "svp"
	IsAlpha  bool
	Children []*Token // Children in the dependency tree
}

// Doc имитирует spaCy.Doc
type Doc struct {
	Tokens   []*Token
	Sentences []string // Simple string representation of sentences
}

// MockNLP симулирует объект nlp спаси.
// В реальном приложении, nlp должен быть интерфейсом, который мог бы быть реализован
// например, как RestClient или PythonSubprocessWrapper.
type MockNLP struct {
	language string
}

// Process симулирует nlp(text) и возвращает Doc.
// В реальном приложении здесь будет логика вызова внешнего spaCy.
func (m *MockNLP) Process(text string) (*Doc, error) {
	// Это очень упрощенная симуляция.
	// Реальная обработка spaCy потребовала бы гораздо более сложной логики
	// или, что более вероятно, вызова внешнего Python-процесса/сервиса.
	// Например, для получения 'svp' и 'rights'/'children' нужны полноценные dependency parsing.

	// Пример: Если текст "Ich rufe Peter an." (German separable verb)
	// spaCy выдаст:
	// Token: "rufe", Lemma: "rufen", POS: "VERB", Dep: "ROOT", Children: [Token "an" (Dep: "svp")]
	// Token: "an", Lemma: "an", POS: "ADP", Dep: "svp"

	// Здесь мы просто разбиваем по пробелам и делаем базовую лемматизацию/POS-тегирование.
	// Заглушка для svp:
	if m.language == "de" && strings.Contains(text, "rufe") && strings.Contains(text, "an") {
		// ОЧЕНЬ УПРОЩЕННО:
		tokens := []*Token{
			{Text: "Ich", Lemma: "ich", POS: "PRON", IsAlpha: true},
			{Text: "rufe", Lemma: "rufen", POS: "VERB", Dep: "ROOT", IsAlpha: true, Children: []*Token{{Text: "an", Lemma: "an", POS: "ADP", Dep: "svp", IsAlpha: true}}},
			{Text: "Peter", Lemma: "Peter", POS: "PROPN", IsAlpha: true},
			{Text: "an", Lemma: "an", POS: "ADP", Dep: "svp", IsAlpha: true},
			{Text: ".", Lemma: ".", POS: "PUNCT", IsAlpha: false},
		}
		return &Doc{Tokens: tokens, Sentences: []string{text}}, nil
	} else if m.language == "de" {
		// Очень базовая лемматизация для немецкого, без svp
		tokens := make([]*Token, 0)
		for _, word := range strings.Fields(text) {
			cleanWord := strings.Trim(word, ".,!?;:")
			if cleanWord == "" {
				continue
			}
			pos := "NOUN"
			if strings.HasSuffix(cleanWord, "en") || strings.HasSuffix(cleanWord, "e") {
				pos = "VERB" // Простое предположение
			}
			tokens = append(tokens, &Token{Text: cleanWord, Lemma: strings.ToLower(cleanWord), POS: pos, IsAlpha: true})
		}
		return &Doc{Tokens: tokens, Sentences: []string{text}}, nil
	}


	// Для английского просто базовая лемматизация
	tokens := make([]*Token, 0)
	for _, word := range strings.Fields(text) {
		cleanWord := strings.Trim(word, ".,!?;:")
		if cleanWord == "" {
			continue
		}
		pos := "NOUN"
		if strings.HasSuffix(cleanWord, "ing") || strings.HasSuffix(cleanWord, "ed") {
			pos = "VERB" // Простое предположение
		}
		tokens = append(tokens, &Token{Text: cleanWord, Lemma: strings.ToLower(cleanWord), POS: pos, IsAlpha: true})
	}
	return &Doc{Tokens: tokens, Sentences: []string{text}}, nil
}

var nlp *MockNLP // Глобальный объект NLP

// --- Функции, адаптированные из Python ---

// getVerbWithParticle проверяет, есть ли у глагола отделяемая приставка, и объединяет их.
func getVerbWithParticle(token *Token) string {
	if token.POS == "VERB" {
		for _, particle := range token.Children {
			if particle.Dep == "svp" { // svp = separable verb prefix
				return fmt.Sprintf("%s%s", particle.Text, token.Lemma)
			}
		}
	}
	return token.Lemma
}

// getOriginalFormWithParticle возвращает исходную форму с частицей, если применимо.
func getOriginalFormWithParticle(token *Token) string {
	if token.POS == "VERB" {
		for _, child := range token.Children {
			if child.Dep == "svp" {
				return fmt.Sprintf("%s %s", token.Text, child.Text)
			}
		}
	}
	return token.Text
}

// loadLemmaIndex загружает индекс лемм из CSV файла.
func loadLemmaIndex(filePath string) (map[string]int, error) {
	lemmaIndex := make(map[string]int)
	file, err := os.Open(filePath)
	if err != nil {
		return nil, fmt.Errorf("file not found: %s, error: %w", filePath, err)
	}
	defer file.Close()

	reader := csv.NewReader(file)
	// reader.Comma = ',' // По умолчанию, но если TSV, то '\t'
	// reader.FieldsPerRecord = -1 // Для строк с разным количеством полей

	for lineNumber := 0; ; lineNumber++ {
		row, err := reader.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("error reading file %s at line %d: %w", filePath, lineNumber+1, err)
		}
		if len(row) > 0 {
			word := row[0]
			if _, exists := lemmaIndex[word]; !exists {
				lemmaIndex[word] = lineNumber
			}
		}
	}
	return lemmaIndex, nil
}

// readInputText читает весь текст из файла.
func readInputText(inputFile string) (string, error) {
	content, err := os.ReadFile(inputFile)
	if err != nil {
		return "", fmt.Errorf("error reading file %s: %w", inputFile, err)
	}
	return string(content), nil
}

// processSentenceLemmas извлекает и сортирует леммы из предложения.
func processSentenceLemmas(sentence string, lemmaIndex map[string]int, nlp *MockNLP) ([]string, error) {
	doc, err := nlp.Process(sentence)
	if err != nil {
		return nil, fmt.Errorf("NLP processing error: %w", err)
	}

	sentenceTokensSet := make(map[string]struct{})

	for _, token := range doc.Tokens {
		if token.IsAlpha && token.Dep != "svp" {
			if token.POS == "VERB" {
				verbForm := getVerbWithParticle(token)
				sentenceTokensSet[verbForm] = struct{}{}
			} else {
				sentenceTokensSet[token.Lemma] = struct{}{}
			}
		}
	}

	var sortedTokens []string
	for token := range sentenceTokensSet {
		sortedTokens = append(sortedTokens, token)
	}

	// Sort tokens by frequency index
	sort.Slice(sortedTokens, func(i, j int) bool {
		idxI, okI := lemmaIndex[sortedTokens[i]]
		idxJ, okJ := lemmaIndex[sortedTokens[j]]

		if !okI && !okJ { // Both not found, sort alphabetically
			return sortedTokens[i] < sortedTokens[j]
		}
		if !okI { // i not found, j is found (j comes first)
			return false
		}
		if !okJ { // j not found, i is found (i comes first)
			return true
		}
		return idxI < idxJ
	})

	return sortedTokens, nil
}

// processTextV1 обрабатывает режим "token" с двумя файлами (text1 и text2).
func processTextV1(
	inputText string,
	language string,
	lemmaIndexFile string,
	text1Path string,
	text2Path string,
	detailedOutput bool,
	twoColumnOutput bool,
	htmlOutput bool,
	sentenceContextSize int,
	outputFile string,
	timestamp bool,
	twoColumnOutputToFile bool,
	includeSimpleList bool,
	originalFormInSimpleList bool,
	withFields bool,
	withBr bool,
	pipe bool,
) (string, error) {
	finalOutputFile := outputFile

	lemmaIndex, err := loadLemmaIndex(lemmaIndexFile)
	if err != nil {
		return "", fmt.Errorf("failed to load lemma index: %w", err)
	}

	var text1Lines []string
	if strings.Contains(inputText, "\n") || !fileExists(inputText) { // Проверяем, является ли inputText сырым текстом или файлом
		text1Lines = strings.Split(inputText, "\n")
	} else {
		content, err := readInputText(inputText)
		if err != nil {
			return "", err
		}
		text1Lines = strings.Split(content, "\n")
	}
	text1Lines = cleanLines(text1Lines) // Удаляем пустые строки и обрезаем пробелы

	text2Content, err := readInputText(text2Path)
	if err != nil {
		return "", err
	}
	text2Lines := cleanLines(strings.Split(text2Content, "\n"))

	if len(text1Lines) != len(text2Lines) {
		fmt.Fprintf(os.Stderr, "Warning: Mismatch in line counts - text1: %d, text2: %d\n", len(text1Lines), len(text2Lines))
		minLength := min(len(text1Lines), len(text2Lines))
		text1Lines = text1Lines[:minLength]
		text2Lines = text2Lines[:minLength]
	}

	uniqueLemmatizedTokens := make(map[string]struct{})
	tokenToSentence := make(map[string]struct {
		Index    int
		Sentence string
	})
	tokenToOriginalForm := make(map[string]string)

	for i, line1 := range text1Lines {
		doc, err := nlp.Process(line1)
		if err != nil {
			return "", fmt.Errorf("NLP processing error for line %d: %w", i, err)
		}

		for _, token := range doc.Tokens {
			if token.IsAlpha {
				if token.POS == "VERB" {
					var verbForm string
					if language == "de" {
						verbForm = getVerbWithParticle(token)
					} else {
						verbForm = token.Lemma
					}
					uniqueLemmatizedTokens[verbForm] = struct{}{}
					tokenToSentence[verbForm] = struct {
						Index    int
						Sentence string
					}{i, line1}
					if language == "de" {
						tokenToOriginalForm[verbForm] = getOriginalFormWithParticle(token)
					} else {
						tokenToOriginalForm[verbForm] = token.Text
					}
				} else if token.Dep != "svp" {
					uniqueLemmatizedTokens[token.Lemma] = struct{}{}
					tokenToSentence[token.Lemma] = struct {
						Index    int
						Sentence string
					}{i, line1}
					tokenToOriginalForm[token.Lemma] = token.Text
				}
			}
		}
	}

	var foundTokens []string
	var notFoundTokens []string
	for token := range uniqueLemmatizedTokens {
		if _, ok := lemmaIndex[token]; ok {
			foundTokens = append(foundTokens, token)
		} else {
			notFoundTokens = append(notFoundTokens, token)
		}
	}

	sort.Slice(foundTokens, func(i, j int) bool {
		return lemmaIndex[foundTokens[i]] < lemmaIndex[foundTokens[j]]
	})
	sort.Strings(notFoundTokens)

	finalSortedTokens := append(foundTokens, notFoundTokens...)

	if outputFile != "" {
		if timestamp {
			tsStr := time.Now().Format("20060102150405")
			_, filename := filepath.Split(outputFile)
			finalOutputFile = filepath.Join(filepath.Dir(outputFile), fmt.Sprintf("%s-%s", tsStr, filename))
		}

		file, err := os.Create(finalOutputFile)
		if err != nil {
			return "", fmt.Errorf("failed to create output file: %w", err)
		}
		defer file.Close()

		writer := csv.NewWriter(file)
		writer.Comma = '\t' // TSV

		if withFields {
			writer.Write(getTSVHeader())
		}

		for _, token := range finalSortedTokens {
			sentData := tokenToSentence[token]
			l1Sentence := strings.TrimSpace(sentData.Sentence)
			l2Sentence := strings.TrimSpace(text2Lines[sentData.Index])

			startIndex := max(0, sentData.Index-sentenceContextSize)
			endIndex := min(len(text1Lines), sentData.Index+sentenceContextSize+1)

			l1LeftContext := strings.Join(cleanLines(text1Lines[startIndex:sentData.Index]), " ")
			l1RightContext := strings.Join(cleanLines(text1Lines[sentData.Index+1:endIndex]), " ")
			l2LeftContext := strings.Join(cleanLines(text2Lines[startIndex:sentData.Index]), " ")
			l2RightContext := strings.Join(cleanLines(text2Lines[sentData.Index+1:endIndex]), " ")

			simpleListEntry := ""
			if includeSimpleList {
				lemmas, err := processSentenceLemmas(l1Sentence, lemmaIndex, nlp)
				if err != nil {
					return "", fmt.Errorf("failed to process sentence lemmas for simple list: %w", err)
				}
				if withBr {
					simpleListEntry = strings.Join(lemmas, "<br>")
				} else {
					simpleListEntry = strings.Join(lemmas, "\n")
				}
			}

			originalForm := tokenToOriginalForm[token]
			row := make([]string, 67) // 67 columns for the header

			row[0] = token // Quotation
			row[1] = token // WordSource
			if twoColumnOutputToFile {
				row[2] = originalForm // WordSourceInflectedForm
			} else {
				row[2] = ""
			}
			row[5] = l1LeftContext              // SentenceSourceContextLeft
			row[6] = l1Sentence                 // SentenceSource
			row[7] = l1RightContext             // SentenceSourceContextRight
			row[8] = l2LeftContext              // SentenceDestinationContextLeft
			row[9] = l2Sentence                 // SentenceDestination
			row[10] = l2RightContext            // SentenceDestinationContextRight
			row[11] = simpleListEntry           // SentenceSourceWordlist
			row[12] = l1Sentence                // SentenceSourceCloze
			if language == "de" {
				row[58] = "1" // Source-de-DE
				row[65] = "1" // Destination-de-DE
			} else if language == "en" {
				row[56] = "1" // Source-en-GB
				row[63] = "1" // Destination-en-GB
			}

			writer.Write(row)
		}
		writer.Flush()
		if err := writer.Error(); err != nil {
			return "", fmt.Errorf("error writing TSV: %w", err)
		}
	}

	if !pipe {
		if htmlOutput {
			fmt.Println("<table>")
			for _, token := range finalSortedTokens {
				originalForm := tokenToOriginalForm[token]
				fmt.Printf("<tr><td>%s</td><td>%s</td></tr>\n", token, originalForm)
			}
			fmt.Println("</table>")
		} else if twoColumnOutput {
			for _, token := range finalSortedTokens {
				originalForm := tokenToOriginalForm[token]
				fmt.Printf("%s\t%s\n", token, originalForm)
			}
		} else {
			for _, token := range finalSortedTokens {
				fmt.Println(token)
			}
			fmt.Println() // Empty line to separate the list of tokens
		}

		if detailedOutput {
			for _, token := range finalSortedTokens {
				sentData := tokenToSentence[token]
				l1Sentence := strings.TrimSpace(sentData.Sentence)
				startIndex := max(0, sentData.Index-sentenceContextSize)
				endIndex := min(len(text1Lines), sentData.Index+sentenceContextSize+1)

				l1LeftContext := strings.Join(cleanLines(text1Lines[startIndex:sentData.Index]), " ")
				l1RightContext := strings.Join(cleanLines(text1Lines[sentData.Index+1:endIndex]), " ")

				fmt.Println(token)
				if l1LeftContext != "" {
					fmt.Println(l1LeftContext)
				}
				fmt.Println(l1Sentence)
				if l1RightContext != "" {
					fmt.Println(l1RightContext)
				}
				fmt.Println()
			}
		}
	}
	return finalOutputFile, nil
}

// processTextV2 обрабатывает режим "token" с одним файлом (input_text).
func processTextV2(
	inputText string,
	language string,
	lemmaIndexFile string,
	detailedOutput bool,
	twoColumnOutput bool,
	htmlOutput bool,
	sentenceContextSize int,
	outputFile string,
	timestamp bool,
	twoColumnOutputToFile bool,
	includeSimpleList bool,
	originalFormInSimpleList bool,
	withFields bool,
	withBr bool,
	pipe bool,
) (string, error) {
	finalOutputFile := outputFile

	lemmaIndex, err := loadLemmaIndex(lemmaIndexFile)
	if err != nil {
		return "", fmt.Errorf("failed to load lemma index: %w", err)
	}

	doc, err := nlp.Process(inputText)
	if err != nil {
		return "", fmt.Errorf("NLP processing error: %w", err)
	}

	uniqueLemmatizedTokens := make(map[string]struct{})
	tokenToSentence := make(map[string]struct {
		Index    int
		Sentence string
	})
	tokenToOriginalForm := make(map[string]string)

	for sentIndex, sentText := range doc.Sentences { // Iterating over simulated sentences
		// Re-process sentence to get tokens with correct sentence context if necessary for this mock
		sentDoc, err := nlp.Process(sentText)
		if err != nil {
			return "", fmt.Errorf("NLP processing error for sentence %d: %w", sentIndex, err)
		}

		for _, token := range sentDoc.Tokens {
			if token.IsAlpha {
				if token.POS == "VERB" {
					var verbForm string
					if language == "de" {
						verbForm = getVerbWithParticle(token)
					} else {
						verbForm = token.Lemma
					}
					uniqueLemmatizedTokens[verbForm] = struct{}{}
					tokenToSentence[verbForm] = struct {
						Index    int
						Sentence string
					}{sentIndex, sentText}
					if language == "de" {
						tokenToOriginalForm[verbForm] = getOriginalFormWithParticle(token)
					} else {
						tokenToOriginalForm[verbForm] = token.Text
					}
				} else if token.Dep != "svp" {
					uniqueLemmatizedTokens[token.Lemma] = struct{}{}
					tokenToSentence[token.Lemma] = struct {
						Index    int
						Sentence string
					}{sentIndex, sentText}
					tokenToOriginalForm[token.Lemma] = token.Text
				}
			}
		}
	}

	var foundTokens []string
	var notFoundTokens []string
	for token := range uniqueLemmatizedTokens {
		if _, ok := lemmaIndex[token]; ok {
			foundTokens = append(foundTokens, token)
		} else {
			notFoundTokens = append(notFoundTokens, token)
		}
	}

	sort.Slice(foundTokens, func(i, j int) bool {
		return lemmaIndex[foundTokens[i]] < lemmaIndex[foundTokens[j]]
	})
	sort.Strings(notFoundTokens)

	finalSortedTokens := append(foundTokens, notFoundTokens...)

	if outputFile != "" {
		if timestamp {
			tsStr := time.Now().Format("20060102150405")
			_, filename := filepath.Split(outputFile)
			finalOutputFile = filepath.Join(filepath.Dir(outputFile), fmt.Sprintf("%s-%s", tsStr, filename))
		}

		file, err := os.Create(finalOutputFile)
		if err != nil {
			return "", fmt.Errorf("failed to create output file: %w", err)
		}
		defer file.Close()

		writer := csv.NewWriter(file)
		writer.Comma = '\t' // TSV

		if withFields {
			writer.Write(getTSVHeader())
		}

		for _, token := range finalSortedTokens {
			sentData := tokenToSentence[token]
			l1Sentence := strings.TrimSpace(sentData.Sentence)

			// Get context sentences from doc.Sentences (simulated)
			sentences := doc.Sentences
			startIndex := max(0, sentData.Index-sentenceContextSize)
			endIndex := min(len(sentences), sentData.Index+sentenceContextSize+1)

			l1LeftContext := strings.Join(sentences[startIndex:sentData.Index], " ")
			l1RightContext := strings.Join(sentences[sentData.Index+1:endIndex], " ")

			simpleListEntry := ""
			if includeSimpleList {
				lemmas, err := processSentenceLemmas(l1Sentence, lemmaIndex, nlp)
				if err != nil {
					return "", fmt.Errorf("failed to process sentence lemmas for simple list: %w", err)
				}

				if originalFormInSimpleList {
					var entries []string
					for _, lemma := range lemmas {
						original := tokenToOriginalForm[lemma] // This might be wrong if lemma is not in the map
						if original == "" { // Fallback if original form not found for a lemma
							original = lemma
						}
						if withBr {
							entries = append(entries, fmt.Sprintf("%s<br>%s", lemma, original))
						} else {
							entries = append(entries, fmt.Sprintf("%s\t%s", lemma, original))
						}
					}
					simpleListEntry = strings.Join(entries, "<br>")
				} else {
					if withBr {
						simpleListEntry = strings.Join(lemmas, "<br>")
					} else {
						simpleListEntry = strings.Join(lemmas, "\n")
					}
				}
			}

			originalForm := tokenToOriginalForm[token]
			row := make([]string, 67) // 67 columns for the header

			row[0] = token // Quotation
			row[1] = token // WordSource
			if twoColumnOutputToFile {
				row[2] = originalForm // WordSourceInflectedForm
			} else {
				row[2] = ""
			}
			row[5] = l1LeftContext      // SentenceSourceContextLeft
			row[6] = l1Sentence         // SentenceSource
			row[7] = l1RightContext     // SentenceSourceContextRight
			row[11] = simpleListEntry   // SentenceSourceWordlist
			row[12] = l1Sentence        // SentenceSourceCloze

			if language == "de" {
				row[58] = "1" // Source-de-DE
				row[65] = "1" // Destination-de-DE
			} else if language == "en" {
				row[56] = "1" // Source-en-GB
				row[63] = "1" // Destination-en-GB
			}

			writer.Write(row)
		}
		writer.Flush()
		if err := writer.Error(); err != nil {
			return "", fmt.Errorf("error writing TSV: %w", err)
		}
	}

	if !pipe {
		if htmlOutput {
			fmt.Println("<table>")
			for _, token := range finalSortedTokens {
				originalForm := tokenToOriginalForm[token]
				fmt.Printf("<tr><td>%s</td><td>%s</td></tr>\n", token, originalForm)
			}
			fmt.Println("</table>")
		} else if twoColumnOutput {
			for _, token := range finalSortedTokens {
				originalForm := tokenToOriginalForm[token]
				fmt.Printf("%s\t%s\n", token, originalForm)
			}
		} else {
			for _, token := range finalSortedTokens {
				fmt.Println(token)
			}
			fmt.Println()
		}

		if detailedOutput {
			for _, token := range finalSortedTokens {
				sentData := tokenToSentence[token]
				l1Sentence := strings.TrimSpace(sentData.Sentence)

				sentences := doc.Sentences // From simulated doc.Sentences
				startIndex := max(0, sentData.Index-sentenceContextSize)
				endIndex := min(len(sentences), sentData.Index+sentenceContextSize+1)

				l1LeftContext := strings.Join(sentences[startIndex:sentData.Index], " ")
				l1RightContext := strings.Join(sentences[sentData.Index+1:endIndex], " ")

				fmt.Println(token)
				if l1LeftContext != "" {
					fmt.Println(l1LeftContext)
				}
				fmt.Println(l1Sentence)
				if l1RightContext != "" {
					fmt.Println(l1RightContext)
				}
				fmt.Println()
			}
		}
	}
	return finalOutputFile, nil
}

// processSentences обрабатывает режим "sentence".
func processSentences(
	language string,
	lemmaIndexFile string,
	text1Path string,
	text2Path string,
	sentenceContextSize int,
	outputFile string,
	timestamp bool,
	includeSimpleList bool,
	withFields bool,
	withBr bool,
) (string, error) {
	finalOutputFile := outputFile

	if outputFile == "" {
		return "", errors.New("output file is required for sentence mode")
	}

	// Load lemma index if simple list is requested
	lemmaIndex := make(map[string]int)
	var err error
	if includeSimpleList {
		lemmaIndex, err = loadLemmaIndex(lemmaIndexFile)
		if err != nil {
			return "", fmt.Errorf("failed to load lemma index: %w", err)
		}
	}

	text1Lines, err := readLines(text1Path)
	if err != nil {
		return "", fmt.Errorf("failed to read text1: %w", err)
	}
	text2Lines, err := readLines(text2Path)
	if err != nil {
		return "", fmt.Errorf("failed to read text2: %w", err)
	}

	if len(text1Lines) != len(text2Lines) {
		fmt.Fprintf(os.Stderr, "Warning: Line count mismatch - Text1: %d, Text2: %d\n", len(text1Lines), len(text2Lines))
		minLength := min(len(text1Lines), len(text2Lines))
		text1Lines = text1Lines[:minLength]
		text2Lines = text2Lines[:minLength]
	}

	if timestamp {
		tsStr := time.Now().Format("20060102150405")
		_, filename := filepath.Split(outputFile)
		finalOutputFile = filepath.Join(filepath.Dir(outputFile), fmt.Sprintf("%s-%s", tsStr, filename))
	}

	file, err := os.Create(finalOutputFile)
	if err != nil {
		return "", fmt.Errorf("failed to create output file: %w", err)
	}
	defer file.Close()

	writer := csv.NewWriter(file)
	writer.Comma = '\t' // TSV

	if withFields {
		writer.Write(getTSVHeader())
	}

	for i := 0; i < len(text1Lines); i++ {
		l1Sentence := strings.TrimSpace(text1Lines[i])
		l2Sentence := strings.TrimSpace(text2Lines[i])

		startIndex := max(0, i-sentenceContextSize)
		endIndex := min(len(text1Lines), i+sentenceContextSize+1)

		l1LeftContext := strings.Join(cleanLines(text1Lines[startIndex:i]), " ")
		l1RightContext := strings.Join(cleanLines(text1Lines[i+1:endIndex]), " ")
		l2LeftContext := strings.Join(cleanLines(text2Lines[startIndex:i]), " ")
		l2RightContext := strings.Join(cleanLines(text2Lines[i+1:endIndex]), " ")

		simpleListEntry := ""
		if includeSimpleList {
			lemmas, err := processSentenceLemmas(l1Sentence, lemmaIndex, nlp)
			if err != nil {
				return "", fmt.Errorf("failed to process sentence lemmas for simple list: %w", err)
			}
			if withBr {
				simpleListEntry = strings.Join(lemmas, "<br>")
			} else {
				simpleListEntry = strings.Join(lemmas, "\n")
			}
		}

		row := make([]string, 67) // 67 columns for the header
		row[0] = l1Sentence          // Quotation
		row[5] = l1LeftContext       // SentenceSourceContextLeft
		row[6] = l1Sentence          // SentenceSource
		row[7] = l1RightContext      // SentenceSourceContextRight
		row[8] = l2LeftContext       // SentenceDestinationContextLeft
		row[9] = l2Sentence          // SentenceDestination
		row[10] = l2RightContext     // SentenceDestinationContextRight
		row[11] = simpleListEntry    // SentenceSourceWordlist
		row[12] = l1Sentence         // SentenceSourceCloze

		if language == "de" {
			row[58] = "1" // Source-de-DE
			row[65] = "1" // Destination-de-DE
		} else if language == "en" {
			row[56] = "1" // Source-en-GB
			row[63] = "1" // Destination-en-GB
		}
		writer.Write(row)
	}

	writer.Flush()
	if err := writer.Error(); err != nil {
		return "", fmt.Errorf("error writing TSV: %w", err)
	}

	return finalOutputFile, nil
}

// --- Вспомогательные функции ---

func cleanLines(lines []string) []string {
	var cleaned []string
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if trimmed != "" {
			cleaned = append(cleaned, trimmed)
		}
	}
	return cleaned
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return !os.IsNotExist(err)
}

func readLines(filePath string) ([]string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	var lines []string
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		lines = append(lines, scanner.Text())
	}
	return lines, scanner.Err()
}

// getTSVHeader возвращает заголовок для TSV файла.
func getTSVHeader() []string {
	return []string{
		"Quotation", "WordSource", "WordSourceInflectedForm", "WordDestination", "WordSourceContext",
		"SentenceSourceContextLeft", "SentenceSource", "SentenceSourceContextRight",
		"SentenceDestinationContextLeft", "SentenceDestination", "SentenceDestinationContextRight",
		"SentenceSourceWordlist", "SentenceSourceCloze", "SentenceSourceRewriteAISentenceSource",
		"SentenceSourceRewriteAISentenceDestination", "WordSourceMorphologyAI", "Note", "WordRussian",
		"WordUkrainian", "WordEnglish", "WordGerman", "WordSourceMorphemeFirst",
		"WordSourceMorphemeFirstDefinition", "WordSourceMorphemeSecond", "WordSourceMorphemeSecondDefinition",
		"WordSourceMorphemeThird", "WordSourceMorphemeThirdDefinition", "WordSourceMorphemeFourth",
		"WordSourceMorphemeFourthDefinition", "WordSourceMorphemeFifth", "WordSourceMorphemeFifthDefinition",
		"WordSourceIPA", "WordSourceSynonymAI", "WordSourceDefinitionAISentenceSource",
		"WordSourceDefinitionAISentenceDestination", "WordSourceDefinitionFirst", "WordSourceDefinitionFirstClipping",
		"WordSourceDefinitionSecond", "WordDestinationDefinitionFirst", "WordDestinationDefinitionSecond",
		"WordSourceAudio", "SentenceSourceIPA", "SentenceSourceAudio", "Image", "WordSourceCloze",
		"WordSourceContextAI", "TextSource", "TextDestination", "TextSourceURL", "SentenceEnglish",
		"SentenceGerman", "SentenceUkrainian", "SentenceRussian", "Source", "SourceURL", "SeparatorAudio",
		"Source-en-GB", "Source-en-US", "Source-de-DE", "Source-uk-UA", "Source-ru-RU",
		"Destination-en-GB", "Destination-en-US", "Destination-de-DE", "Destination-uk-UA", "Destination-ru-RU",
	}
}

func main() {
	var (
		processType                string
		language                   string
		lemmaIndexFile             string
		text                       string
		text1Path                  string
		text2Path                  string
		detailed                   bool
		twoColumnOutput            bool
		html                       bool
		sentenceContextSize        int
		output                     string
		timestamp                  bool
		twoColumnOutputToFile      bool
		includeSimpleList          bool
		originalFormInSimpleList bool
		withFields                 bool
		withBr                     bool
		pipe                       bool
	)

	flag.StringVar(&processType, "type", "", "Type of processing: token or sentence (required)")
	flag.StringVar(&language, "language", "de", "Language for processing (default: de)")
	flag.StringVar(&lemmaIndexFile, "lemma-index-file", "", "Path to the lemma index CSV file")
	flag.StringVar(&text, "text", "", "Input text to process")
	flag.StringVar(&text1Path, "text1", "", "Path to input text file to process")
	flag.StringVar(&text2Path, "text2", "", "Path to the second text file (e.g., translations)")
	flag.BoolVar(&detailed, "detailed", false, "STDOUT: Enable detailed output in console with sentence and context")
	flag.BoolVar(&twoColumnOutput, "two-column-output", false, "STDOUT: Output tokens in two columns: token and original form")
	flag.BoolVar(&html, "html", false, "STDOUT: Output tokens in an HTML table")
	flag.IntVar(&sentenceContextSize, "sentence-context-size", 1, "CSV: Number of sentences to include before and after the target sentence (default: 1)")
	flag.StringVar(&output, "output", "", "CSV: Output TSV file path for saving results")
	flag.BoolVar(×tamp, "timestamp", false, "CSV: Prepend timestamp to the output file name")
	flag.BoolVar(&twoColumnOutputToFile, "two-column-output-to-file", false, "CSV: Include original forms in the TSV output file when writing to file")
	flag.BoolVar(&includeSimpleList, "include-simple-list", false, "CSV: Include a simple list of tokens in the last column of the output file")
	flag.BoolVar(&originalFormInSimpleList, "original-form-in-simple-list", false, "CSV: Include original forms in the simple list entry in the TSV file")
	flag.BoolVar(&withFields, "with-fields", false, "CSV: Include field names as the first row in the output TSV file")
	flag.BoolVar(&withBr, "with-br", false, "Replace tabs with <br> in the simple list entry")
	flag.BoolVar(&pipe, "pipe", false, "Enable pipeline mode - outputs TSV filename to stdout when using --output")

	flag.Parse()

	// Валидация аргументов
	if processType == "" {
		fmt.Fprintf(os.Stderr, "Error: --type is required.\n")
		flag.Usage()
		os.Exit(1)
	}
	if processType != "token" && processType != "sentence" {
		fmt.Fprintf(os.Stderr, "Error: Invalid --type specified. Must be 'token' or 'sentence'.\n")
		flag.Usage()
		os.Exit(1)
	}

	if language != "de" && language != "en" {
		fmt.Fprintf(os.Stderr, "Error: Invalid --language specified. Must be 'de' or 'en'.\n")
		flag.Usage()
		os.Exit(1)
	}

	// Инициализация симулированного NLP объекта
	nlp = &MockNLP{language: language}

	var finalOutputFile string
	var err error

	if processType == "token" {
		var input string
		if text != "" && text1Path != "" {
			fmt.Fprintf(os.Stderr, "Error: Both --text and --text1 cannot be specified simultaneously.\n")
			os.Exit(1)
		} else if text != "" {
			input = text
		} else if text1Path != "" {
			input, err = readInputText(text1Path)
			if err != nil {
				fmt.Fprintf(os.Stderr, "Error: %v\n", err)
				os.Exit(1)
			}
		} else {
			fmt.Fprintf(os.Stderr, "Error: Either --text or --text1 must be specified for token mode.\n")
			os.Exit(1)
		}

		if text2Path != "" {
			finalOutputFile, err = processTextV1(
				input, language, lemmaIndexFile, text1Path, text2Path, detailed, twoColumnOutput,
				html, sentenceContextSize, output, timestamp, twoColumnOutputToFile,
				includeSimpleList, originalFormInSimpleList, withFields, withBr, pipe,
			)
		} else {
			finalOutputFile, err = processTextV2(
				input, language, lemmaIndexFile, detailed, twoColumnOutput, html,
				sentenceContextSize, output, timestamp, twoColumnOutputToFile,
				includeSimpleList, originalFormInSimpleList, withFields, withBr, pipe,
			)
		}
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error processing tokens: %v\n", err)
			os.Exit(1)
		}

	} else if processType == "sentence" {
		if text1Path == "" || text2Path == "" {
			fmt.Fprintf(os.Stderr, "Error: Both --text1 and --text2 must be specified for sentence mode.\n")
			os.Exit(1)
		}
		if output == "" {
			fmt.Fprintf(os.Stderr, "Error: --output is required for sentence mode.\n")
			os.Exit(1)
		}

		finalOutputFile, err = processSentences(
			language, lemmaIndexFile, text1Path, text2Path, sentenceContextSize,
			output, timestamp, includeSimpleList, withFields, withBr,
		)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error processing sentences: %v\n", err)
			os.Exit(1)
		}
	}

	if pipe && finalOutputFile != "" {
		fmt.Println(filepath.Base(finalOutputFile))
	}
}
