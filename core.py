import nltk
import docx2txt

from nltk.corpus import stopwords
from nltk import WordPunctTokenizer
from nltk.util import ngrams

from string import punctuation

from gensim.models import TfidfModel
from gensim.corpora import Dictionary
from gensim.similarities import MatrixSimilarity
from gensim.models import LsiModel

import numpy as np

import rank_bm25

import pprint
import json

nltk.download("stopwords")
tokenizer = WordPunctTokenizer()
stemmer = nltk.stem.SnowballStemmer('russian')
russian_stopwords = stopwords.words("russian")
with open('syn_map.json', 'r', encoding='utf-8') as fp:
    syn_map = json.load(fp)


def load_doc(filename):
    '''

    загружаем файл в формате docx,
    разделяем его на отдельные параграфы\абзацы
    и удаляем пустые абзацы.
    Выводит массив, содержащий
    параграфы с формате строк

    '''

    doc = docx2txt.process(filename)
    lines = doc.split('\n')
    lines = [line for line in lines if line != '']

    return lines


def get_metadata(json_file, encoding='utf8'):
    """
    На вход: json-файл со словарем {индекс параграфа: [ФЗ, Глава, Статья, пункт]
    Возвращает метаданные (названия статей и глав) в формате: ['строка1', 'строка2',...]

    """
    with open(json_file, 'r', encoding=encoding) as fp:
        data = json.load(fp)
    metadata = []
    for key, item in data.items():
        if len(item) > 3:
            metadata.append(" ".join(item[1:3]))
        else:
            metadata.append(item[1])
    return metadata


def build_bigrams(corpus):
    '''

    Функция для построения биграмм слов в документах.
    На выходе: массив из подмассивов,
    в каждом подмассиве список биграмм из данного параграфа

    '''

    corpus_2grams = []
    for doc in corpus:
        doc_2grams = list(ngrams(doc, 2))
        doc_2grams = ['_'.join(list(bigram)) for bigram in doc_2grams]
        corpus_2grams.append(doc_2grams)
    return corpus_2grams


def preprocess_corpus(lines, bigrams=False):
    '''

    предобрабатываем массив параграфов: токенизируем,
    удаляем стоп-слова, пустые строки, знаки препинания,
    удаляем окончания слов.
    на выходе: массив из под-массивов.
    В одном под-массиве содержатся отдельные слова параграфа в формате строки
    если bigrams=True, функция выдаёт массив подмассивов,
    где в одном подмассиве находятся биграммы слов одного параграфа

    '''

    corp = []
    for parag in lines:
        paragraph = []
        parag = tokenizer.tokenize(parag)
        for word in parag:
            if word not in russian_stopwords and \
                    word != ' ' and \
                    word.strip() not in punctuation and \
                    word.strip()[-1] not in punctuation:
                word = word.lower()
                stemmed_word = stemmer.stem(word)
                paragraph.append(stemmed_word)

        corp.append(paragraph)
    if bigrams:
        corp_bigrams = build_bigrams(corp)
        return corp_bigrams
    else:
        return corp


def preprocess_query(query, bigrams=False):
    '''

    Предобрабатываем запрос по тому же шаблону,
    что и для целого документа.
    На вход: пользовательский запрос в формате строки; на выход:
    Массив из предобработанных слов запроса
    Если bigrams=True, то функция выдаёт биграммы слов в запросе

    '''

    query = ' '.join(tokenizer.tokenize(query))
    query_text = []
    for word in query.split():
        if word not in russian_stopwords and word != ' ' and word.strip() not in punctuation and word.strip()[-1] not in punctuation:
            word = word.lower()
            stemmed_word = stemmer.stem(word)
            #если выражение из запроса в словаре syn_map, то оно заменяется на выражение из закона
            #пока может заменять только слова, а не словосочетания
            if stemmed_word in syn_map.keys():
                stemmed_word = syn_map[stemmed_word]
                if isinstance(stemmed_word, list):
                    for s_w in stemmed_word:
                        query_text.append(s_w)
            else:
                query_text.append(stemmed_word)
    if bigrams:
        query_bigrams = list(ngrams(query_text, 2))
        query_bigrams = ['_'.join(list(bigram)) for bigram in query_bigrams]
        return query_bigrams

    else:
        return query_text


def build_tfidf_or_lsi(corpus, method='tfidf'):
    '''

    построение модели для ранжирования документов.
    На вход: корпус текстов и метод ("tfidf" или "lsi").
    На выход кортеж: (словарь
    терминов в корпусе текстов,
    оцененная модель и матрица сходств слов)

    '''

    dictionary = Dictionary(corpus)
    corpus_bow = [dictionary.doc2bow(doc) for doc in corpus]
    model_tfidf = TfidfModel(corpus_bow)
    corpus_tfidf = [model_tfidf[doc] for doc in corpus_bow]
    simil_tfidf = MatrixSimilarity(corpus_tfidf)
    if method == 'tfidf':

        return dictionary, model_tfidf, simil_tfidf

    elif method == 'lsi':

        model_lsi = LsiModel(corpus_tfidf, id2word=dictionary, num_topics=50)
        corpus_lsi = [model_lsi[doc] for doc in corpus_bow]
        simil_lsi = MatrixSimilarity(corpus_lsi)

        return dictionary, model_lsi, simil_lsi


def top_docs_tfidf(query, dictionary, model, similarity, ntop=4):
    '''

    Находим топ N документов,
    наиболее близких запросу по критерию cosine similarity.
    На вход: пользовательский запрос в формате сторки,
    словарь слов корпуса, модель tfidf и матрица сходств слов
    (берется из функии build_tfidf_or_lsi)
    На выходе: Отсортированный массив из кортежей с
    (номер параграфа, значение cosine similarity)

    '''

    query_corp = dictionary.doc2bow(preprocess_query(query))
    query_tfidf = model[query_corp]
    query_simil = enumerate(similarity[query_tfidf])
    query_top_docs = sorted(query_simil, key=lambda k: -k[1])
    if len(query_top_docs) > ntop:
        query_top_docs = query_top_docs[:ntop]
    else:
        query_top_docs = query_top_docs

    top_docs_indices = [elem[0] for elem in query_top_docs]
    return top_docs_indices


def top_docs_lsi(query, dictionary, model, similarity, ntop=6):
    '''

    Находим топ N документов,
    наиболее близких запросу по критерию cosine similarity.
    На вход: пользовательский запрос в формате сторки,
    словарь слов корпуса, модель lsi и матрица сходств слов
    (берется из функии build_tfidf_or_lsi)
    На выходе: Отсортированный массив из кортежей с
    (номер параграфа, значение cosine similarity)

    '''

    query_corp = dictionary.doc2bow(preprocess_query(query))
    query_lsi = model[query_corp]
    query_simil = enumerate(similarity[query_lsi])
    query_top_docs = sorted(query_simil, key=lambda k: -k[1])
    if len(query_top_docs) > ntop:
        query_top_docs = query_top_docs[:ntop]
    else:
        query_top_docs = query_top_docs
    top_docs_indices = [elem[0] for elem in query_top_docs]
    return top_docs_indices

def top_docs_bm25okapi(query, corp, ntop=6):
    '''На вход: запрос в формате строки, предобработанный корпус текстов и количество релевантных документов в выдаче.
    На выход: индексы топ-N параграфов документа в формате массива'''
    bm25okapi = rank_bm25.BM25Okapi(corp)
    top_docs_indices = np.argsort((bm25okapi.get_scores(preprocess_query(query))))[::-1][:ntop]
    top_docs_indices = list(top_docs_indices)
    return top_docs_indices


def ranking_with_metadata(query, corpus_text, corpus_meta, weight_meta=0.25, ntop=5):
    """
    query: текстовый запрос
    corpus_text: предобработанный корпус текстов (содержания) параграфов
    corpus_meta: предобработанный корпус метаданных (названий статей и глав)
    weight_meta: веса, которые назначаются рангу документов из метаданных (названий статей и глав)
    возвращает ntop индексов параграфов, ранг которых получен путем взвешивания ранга по поиску по метаданным и ранга по поиску по содержанию
    """

    ranking_text = {}
    for rank, paragraph in enumerate(top_docs_bm25okapi(preprocess_query(query), corpus_text, ntop=len(corpus_text))):
        ranking_text[paragraph] = rank + 1
    ranking_meta = {}
    for rank, paragraph in enumerate(top_docs_bm25okapi(preprocess_query(query), corpus_meta, ntop=len(corpus_meta))):
        ranking_meta[paragraph] = rank + 1
    ranking_ = []
    for paragraph in ranking_text.keys():
        final_ranking = (weight_meta * ranking_meta[paragraph]) + ((1 - weight_meta) * ranking_text[paragraph])
        ranking_.append(tuple([final_ranking, paragraph]))
    ranking_final = [x[1] for x in sorted(ranking_, key=lambda x: x[0])]

    return ranking_final[:ntop]


def display_passages_from_doc(query, doc, corp, corp_meta, method='bm25okapi'):

    '''Вывод индекса и текста для топ-N пунктов из документа по критерию релевантности запросу.
        На вход: текстовый запрос в формате строки, документ до предобработки и метод ранжирования пунктов документа
        На выход: индекс и текст пунктов из документа, разделенных пустой строкой'''

    if method == 'tfidf':
        index_string = top_docs_tfidf(query, dictionary, model_tfidf, simil_tfidf)
        for idx in index_string:
            answer = str(idx) + ': ' + doc[idx]
            pprint.pprint(answer)
            print('\n')
    elif method == 'lsi':
        index_string = top_docs_lsi(query, dictionary, model_lsi, simil_lsi)
        for idx in index_string:
            answer = str(idx) + ': ' + doc[idx]
            pprint.pprint(answer)
            print('\n')
    elif method == 'bm25okapi':
        index_string = top_docs_bm25okapi(query, corp=corp, ntop=15)
        for idx in index_string:
            answer = str(idx) + ': ' + doc[idx]
            pprint.pprint(answer)
            print('\n')

    elif method == 'w':
        index_string = ranking_with_metadata(query, corpus_text=corp, corpus_meta=corp_meta)
        for idx in index_string:
            answer = str(idx) + ': ' + doc[idx]
            pprint.pprint(answer)
            print('\n')

    else:
        print('Неправильное значение method. Method может принимать значения \'tfidf\', \'lsi\' или \'bm25okapi\'. ')


