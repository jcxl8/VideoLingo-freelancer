import json
import os
import re
from difflib import SequenceMatcher
from core.prompts import get_summary_prompt
import pandas as pd
from core.utils import *
from core.utils.models import _3_2_SPLIT_BY_MEANING, _4_1_TERMINOLOGY

CUSTOM_TERMS_PATH = 'custom_terms.xlsx'
VIDEO_DESCRIPTION_PATH = 'output/video_description.md'

def read_video_description():
    if not os.path.exists(VIDEO_DESCRIPTION_PATH):
        return ""
    with open(VIDEO_DESCRIPTION_PATH, 'r', encoding='utf-8') as file:
        return file.read().strip()

def combine_chunks():
    """Combine the text chunks identified by whisper into a single long text"""
    with open(_3_2_SPLIT_BY_MEANING, 'r', encoding='utf-8') as file:
        sentences = file.readlines()
    cleaned_sentences = [line.strip() for line in sentences]
    combined_text = ' '.join(cleaned_sentences)
    return combined_text[:load_key('summary_length')]  #! Return only the first x characters

def _normalize_token(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())

def _similar(a, b):
    a = _normalize_token(a)
    b = _normalize_token(b)
    if not a or not b:
        return 0
    return SequenceMatcher(None, a, b).ratio()

def _term_matches_sentence(term, sentence):
    term = str(term).strip()
    sentence = str(sentence)
    if not term or term.lower() in sentence.lower():
        return bool(term)

    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", sentence)
    term_parts = re.findall(r"[A-Za-z][A-Za-z'’-]*", term)
    if not words or not term_parts:
        return False

    for part in term_parts:
        if len(part) < 3:
            continue
        for word in words:
            if abs(len(word) - len(part)) > 2:
                continue
            if _similar(word, part) >= 0.72:
                return True
    return False

def extract_description_proper_nouns(video_description, limit=20):
    if not video_description:
        return []
    stopwords = {
        "The", "This", "That", "These", "Those", "After", "Before", "Sunday",
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
        "YouTube", "Video", "Subscribe", "Watch", "Full", "Episode", "Episodes",
        "Official", "Interview", "Channel", "Description",
    }
    candidates = []
    pattern = r"\b[A-Z][A-Za-z'’-]*(?:\s+[A-Z][A-Za-z'’-]*){0,4}\b"
    for match in re.finditer(pattern, video_description):
        candidate = match.group(0).strip()
        parts = candidate.split()
        if candidate in stopwords or all(part in stopwords for part in parts):
            continue
        if len(candidate) < 3:
            continue
        if candidate not in candidates:
            candidates.append(candidate)
    quoted_pattern = r"[\"“”'‘’]([^\"“”'‘’]{3,80})[\"“”'‘’]"
    for match in re.finditer(quoted_pattern, video_description):
        candidate = re.sub(r"\s+", " ", match.group(1)).strip()
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    acronym_pattern = r"\b[A-Z]{2,}(?:-[A-Z0-9]+)?\b"
    for match in re.finditer(acronym_pattern, video_description):
        candidate = match.group(0).strip()
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates[:limit]

def search_things_to_note_in_prompt(sentence):
    """Search for terms to note in the given sentence"""
    with open(_4_1_TERMINOLOGY, 'r', encoding='utf-8') as file:
        things_to_note = json.load(file)
    things_to_note_list = [
        term['src']
        for term in things_to_note['terms']
        if _term_matches_sentence(term.get('src', ''), sentence)
    ]
    if things_to_note_list:
        prompt = '\n'.join(
            f'{i+1}. "{term["src"]}": "{term["tgt"]}",'
            f' meaning: {term["note"]}'
            for i, term in enumerate(things_to_note['terms'])
            if term['src'] in things_to_note_list
        )
        return prompt
    else:
        return None

def get_summary():
    src_content = combine_chunks()
    video_description = read_video_description()
    description_names = extract_description_proper_nouns(video_description)
    custom_terms = pd.read_excel(CUSTOM_TERMS_PATH)
    custom_terms_json = {
        "terms": 
            [
                {
                    "src": str(row.iloc[0]),
                    "tgt": str(row.iloc[1]), 
                    "note": str(row.iloc[2])
                }
                for _, row in custom_terms.iterrows()
            ]
    }
    for name in description_names:
        custom_terms_json["terms"].append({
            "src": name,
            "tgt": name,
            "note": "Proper noun from the video description. If WhisperX produces a similar misspelling in subtitles, normalize it to this exact name."
        })
    if len(custom_terms) > 0:
        rprint(f"📖 Custom Terms Loaded: {len(custom_terms)} terms")
        rprint("📝 Terms Content:", json.dumps(custom_terms_json, indent=2, ensure_ascii=False))
    if description_names:
        rprint(f"📌 Proper nouns from video description: {', '.join(description_names[:10])}")

    summary_prompt = get_summary_prompt(src_content, custom_terms_json, video_description)
    rprint("📝 Summarizing and extracting terminology ...")
    
    def valid_summary(response_data):
        required_keys = {'src', 'tgt', 'note'}
        if 'terms' not in response_data:
            return {"status": "error", "message": "Invalid response format"}
        for term in response_data['terms']:
            if not all(key in term for key in required_keys):
                return {"status": "error", "message": "Invalid response format"}   
        return {"status": "success", "message": "Summary completed"}

    summary = ask_gpt(summary_prompt, resp_type='json', valid_def=valid_summary, log_title='summary')
    summary['terms'].extend(custom_terms_json['terms'])
    
    with open(_4_1_TERMINOLOGY, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=4)

    rprint(f'💾 Summary log saved to → `{_4_1_TERMINOLOGY}`')

if __name__ == '__main__':
    get_summary()
