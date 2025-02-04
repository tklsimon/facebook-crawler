import numpy as np
import re
from datetime import datetime
from dateutil import parser
from typing import Tuple


def is_null_whitespace_or_na(input_str: str) -> bool:
    """
    Check if the string is None, contains whiespace only or NA
    :param:
        input_str: Input string to be checked
    :return:
        True if the string is None, contains whiespace only or NA. Otherwise, return False
    """
    return (input_str is None) or \
        (input_str.strip() == "") or \
        (input_str.upper() == "N/A") or \
        (input_str.upper() == "NA")

def convert_date_format(date_str: str, date_format: str) -> str:
    """
    Convert the string to the desired date format
    :params:
        input_str: Input string
        date_format: Desired date format
    :return:
        String in the desired date format
    """
    try:
        parsed_date = parser.parse(date_str)
        return parsed_date.strftime(date_format)
    except ValueError as e:
        print(f"Value Error: {e}")
        raise

def get_days_from_today(date_str: str, date_format: str='%Y%m%d') -> int:
    """
    Calculate the number of days from a specified date to today.
    :params:
        date_str: The date in string format
        date_format: The format of the input date string
    :return:
        The number of days from the specified date to today
    """
    try:
        today_dt = datetime.now()
        date_dt = datetime.strptime(date_str, date_format)
        return (today_dt - date_dt).days
    except:
        return np.nan

def extract_chinese_english_parts(text: str) -> Tuple[str, str]:
    """
    Extract Chinese and English parts from a given text string.
    :param:
        text: Input string containing Chinese and English text.
    :return: 
        chinese_text: Extracted Chinese characters concatenated together.
        english_text: Extracted English words, separated by spaces.
    """
    chinese_parts = re.compile(r'[\u4e00-\u9fff]+').findall(text)
    english_parts = re.compile(r'[a-zA-Z]+').findall(text)
    
    chinese_text = ''.join(chinese_parts)
    english_text = ' '.join(english_parts)

    return chinese_text, english_text

def levenshtein(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein distance of a pair of words.
    :params:
        s1: Input word to be compared with s2
        s2: Input word to be compared with s1
    :return: 
        The Levenshtein distance between s1 and s2
    """
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def levenshtein_score(s1: str, s2: str) -> float:
    """
    Calculate Levenshtein similarity score of a pair of words.
    :params:
        s1: Input word to be compared with s2
        s2: Input word to be compared with s1
    :return: 
        The Levenshtein similarity score of s1 and s2
    """
    levenshtein_score = 1.0 - levenshtein(s1, s2) / max(len(s1), len(s2))
    return levenshtein_score

def mongo_elkan_score(s1: str, s2: str) -> float:
    """
    Calculate Monge-Elkan similarity score of a pair of strings.
    :params:
        s1: Input string to be compared with s2
        s2: Input string to be compared with s1
    :return: 
        The Monge-Elkan similarity score of s1 and s2
    """
    s1 = re.sub(r'\s+', ' ', s1).upper().strip()
    s2 = re.sub(r'\s+', ' ', s2).upper().strip()

    # Score for english words
    s1_set = set(s1.split(' '))
    s2_set = set(s2.split(' '))
    
    score = 0.0
    if len(s1_set) > len(s2_set):
        (s1_set, s2_set) = (s2_set, s1_set)
    for s1_word in s1_set:
        max_score_temp = 0.0
        for s2_word in s2_set:
            max_score_temp = \
                max(max_score_temp,
                    levenshtein_score(s1_word, s2_word))
        score += max_score_temp
    score /= len(s2_set)
    return score

def string_similarity_score(s1: str, s2: str) -> float:
    """
    Calculate string similarity score of a pair of strings which may contain Chinese and English text.
    :params:
        s1: Input string to be compared with s2
        s2: Input string to be compared with s1
    :return: 
        The string similarity score of s1 and s2
    """
    s1_chi, s1_eng = extract_chinese_english_parts(s1)
    s2_chi, s2_eng = extract_chinese_english_parts(s2)

    len_chi = max(len(s1_chi), len(s2_chi))
    len_eng = max(len(s1_eng.split()), len(s2_eng.split()))
    
    # Calculate the Levenshtein score for Chinese parts
    if len_chi > 0:
        score_chi = levenshtein_score(s1_chi, s2_chi)
    else:
        score_chi = 0.0

    # Calculate the Mongo-Elkan score for English parts
    if len_eng > 0:
        score_eng = mongo_elkan_score(s1_eng, s2_eng)
    else:
        score_eng = 0.0

    # Combine the scores from Chines parts and English parts with weights based on their lengths
    return (score_chi*len_chi + score_eng*len_eng) / (len_chi + len_eng)
