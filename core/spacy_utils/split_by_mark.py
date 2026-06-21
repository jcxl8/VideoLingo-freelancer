import os
import re
import pandas as pd
import warnings
from core.spacy_utils.load_nlp_model import init_nlp, SPLIT_BY_MARK_FILE
from core.utils.config_utils import load_key, get_joiner
from rich import print as rprint

warnings.filterwarnings("ignore", category=FutureWarning)
# English abbreviations that should NOT trigger sentence splitting
_SENTENCE_SPLIT_ABBREVS = {
    # single-word abbreviations (Dr., Mr., etc.)
    "dr", "mr", "mrs", "ms", "prof", "rev", "st", "sr", "jr",
    "etc", "vs", "viz", "inc", "ltd", "corp", "co",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    "dept", "est", "approx", "gen", "capt", "col", "lt", "maj", "sgt",
    # multi-part dotted abbreviations (U.S., U.K., e.g., i.e., Ph.D., etc.)
    # after rstrip(".?!") these become dotted strings like "u.s", "ph.d"
    "u.s", "u.k", "e.u", "u.n", "ph.d", "m.d", "b.a", "m.a",
    "e.g", "i.e", "a.m", "p.m", "a.d", "b.c", "m.sc", "j.d",
}


def _is_person_name_initial_boundary(match, word):
    if not re.fullmatch(r"(?:[A-Z]\.)+", word):
        return False

    text_before = match.string[:match.start()].rstrip()
    tokens_before = text_before.split()
    previous_word = tokens_before[-2].strip(".,!?;:\"'()[]{}") if len(tokens_before) >= 2 else ""
    text_after = match.string[match.end():]

    starts_with_initial_and_surname = bool(
        re.match(r"(?:[A-Z]\.\s+)+[A-Z][A-Za-z'’-]+\b", text_after)
    )
    starts_with_two_name_parts = bool(
        re.match(r"[A-Z][A-Za-z'’-]+\s+[A-Z][A-Za-z'’-]+\b", text_after)
    )
    surrounded_by_name_parts = bool(
        re.fullmatch(r"(?:[A-Z][A-Za-z'’-]+|[A-Z])", previous_word)
        and re.match(r"[A-Z][A-Za-z'’-]+\b", text_after)
    )
    return starts_with_initial_and_surname or starts_with_two_name_parts or surrounded_by_name_parts


def _split_on_sentence_end(input_text):
    """Split text on sentence-ending punctuation (.!? + space + capital letter),
    skipping known abbreviations (Dr., Mr., etc.)."""
    import re

    def _should_replace(match):
        text_before = match.string[:match.start()]
        # Extract the last word before the period (may include the period itself)
        word = text_before.rstrip().rsplit(maxsplit=1)[-1] if text_before.rstrip() else ""
        word_clean = word.rstrip(".!?").lower()
        if word_clean in _SENTENCE_SPLIT_ABBREVS:
            return match.group()  # keep original whitespace — don't split
        if _is_person_name_initial_boundary(match, word):
            return match.group()
        return "\n"  # replace with newline

    # 1. Split on sentence-ending punctuation (.!?)
    input_text = re.sub(r"(?<=[.!?])\s+(?=[A-Z])", _should_replace, input_text)
    # 2. Split before coordinating conjunctions that start new clauses
    #    Match: " And Elon..." (capitalized proper noun) or " And it..." (pronoun subject)
    coord_pattern = r'\s+([Aa]nd|[Bb]ut|[Oo]r|[Ss]o)\s+'
    # 2a. Capitalized word after (e.g., "And Elon")
    input_text = re.sub(coord_pattern + r'(?=[A-Z])', r'\n\1 ', input_text)
    # 2b. Common pronoun subjects after (e.g., "And it", "And he", "And they")
    input_text = re.sub(
        coord_pattern + r'(it|he|she|they|we|I|you|there|this|that|these|those)\b',
        r'\n\1 \2',
        input_text
    )
    return input_text



def split_by_mark(nlp):
    whisper_language = load_key("whisper.language")
    language = load_key("whisper.detected_language") if whisper_language == 'auto' else whisper_language # consider force english case
    joiner = get_joiner(language)
    rprint(f"[blue]🔍 Using {language} language joiner: '{joiner}'[/blue]")
    chunks = pd.read_excel("output/log/cleaned_chunks.xlsx")
    chunks.text = chunks.text.apply(lambda x: x.strip('"').strip(""))
    
    # join with joiner
    input_text = joiner.join(chunks.text.to_list())

    # Pre-split on obvious sentence-ending punctuation before spaCy processing.
    # WhisperX may preserve periods in word-level output, but spaCy sometimes fails
    # to split when period-attached words precede capitalised sentence starts.
    # This regex inserts newlines at ". CapitalLetter", "? CapitalLetter", etc.
    input_text = _split_on_sentence_end(input_text)

    doc = nlp(input_text)
    assert doc.has_annotation("SENT_START")

    # skip - and ...
    sentences_by_mark = []
    current_sentence = []
    
    # iterate all sentences
    for sent in doc.sents:
        text = sent.text.strip()
        
        # check if the current sentence ends with - or ...
        if current_sentence and (
            text.startswith('-') or 
            text.startswith('...') or
            current_sentence[-1].endswith('-') or
            current_sentence[-1].endswith('...')
        ):
            current_sentence.append(text)
        else:
            if current_sentence:
                sentences_by_mark.append(' '.join(current_sentence))
                current_sentence = []
            current_sentence.append(text)
    
    # add the last sentence
    if current_sentence:
        sentences_by_mark.append(' '.join(current_sentence))

    with open(SPLIT_BY_MARK_FILE, "w", encoding="utf-8") as output_file:
        for i, sentence in enumerate(sentences_by_mark):
            if i > 0 and sentence.strip() in [',', '.', '，', '。', '？', '！']:
                # ! If the current line contains only punctuation, merge it with the previous line, this happens in Chinese, Japanese, etc.
                output_file.seek(output_file.tell() - 1, os.SEEK_SET)  # Move to the end of the previous line
                output_file.write(sentence)  # Add the punctuation
            else:
                output_file.write(sentence + "\n")
    
    rprint(f"[green]💾 Sentences split by punctuation marks saved to →  `{SPLIT_BY_MARK_FILE}`[/green]")

if __name__ == "__main__":
    nlp = init_nlp()
    split_by_mark(nlp)
