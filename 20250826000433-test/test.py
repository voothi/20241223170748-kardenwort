# --- Финальный код, основанный на официальной документации ---

# 1. Импортируем нужные функции из установленной библиотеки
from german_compound_splitter import comp_split
import os

print("Библиотека 'german-compound-splitter' успешно импортирована.")

# 2. Указываем имя файла словаря
#    (предполагается, что он лежит в той же папке, что и этот скрипт)
dictionary_file = 'german.dic'

# 3. Проверяем, существует ли файл словаря
if not os.path.exists(dictionary_file):
    print(f"\nОШИБКА: Файл словаря '{dictionary_file}' не найден!")
    print("Пожалуйста, скачайте его и поместите в ту же папку, что и этот ноутбук.")
else:
    print(f"\nНайден файл словаря: '{dictionary_file}'. Загружаем...")
    # Загружаем словарь в специальную структуру данных (автомат Ахо-Корасик)
    # Это нужно сделать только один раз.
    try:
        ahocs = comp_split.read_dictionary_from_file(dictionary_file)
        print("Словарь успешно загружен.")

        # 4. Наше слово для разбора
        compound_word = "Donaudampfschifffahrtsgesellschaftskapitän"

        # 5. Вызываем функцию dissect для разбора слова
        #    Используем `make_singular=True`, чтобы привести части к единственному числу
        dissection = comp_split.dissect(compound_word, ahocs, make_singular=False)

        print("\n" + "="*65)
        print(f"Анализируем слово: '{compound_word}'")
        print("="*65)
        
        # Результат - это кортеж из двух списков. Нас интересует второй.
        # merge_fractions объединяет мелкие части для лучшего результата.
        final_components = comp_split.merge_fractions(dissection)
        
        print("✅✅✅ ПОБЕДА! Слово успешно разделено на компоненты:")
        for i, part in enumerate(final_components, 1):
            print(f"  {i}. {part}")
            
    except Exception as e:
        print(f"\nПроизошла ошибка при чтении словаря: {e}")
        print("Возможно, файл имеет неверную кодировку. Он должен быть в UTF-8.")