import os
import warnings
from core.spacy_utils.load_nlp_model import init_nlp, SPLIT_BY_COMMA_FILE, SPLIT_BY_CONNECTOR_FILE
from core.utils import rprint

warnings.filterwarnings("ignore", category=FutureWarning)

def _is_coordinating_conjunction(lang, token_text):
    """Check if token is a coordinating conjunction (not subordinating)."""
    coord_map = {
        "en": ["and", "but", "or"],
        "zh": [],
        "ja": [],
        "fr": ["et", "ou", "mais"],
        "ru": ["и", "или", "но"],
        "es": ["y", "o", "pero"],
        "de": ["und", "oder", "aber"],
        "it": ["e", "o", "ma"],
    }
    return token_text.lower() in coord_map.get(lang, [])

def _right_side_starts_with_subject(doc, token_i):
    """For a coordinating conjunction, check if the right side is an independent clause
    (subject followed by verb) rather than a compound verb or noun phrase coordination.
    
    Strategy: find a noun/pronoun first (accepting that spaCy may mislabel its dep_ as 'conj'
    when the conjunction connects two clauses), then verify a verb appears after it."""
    found_subject = False
    for i in range(token_i + 1, len(doc)):
        tok = doc[i]
        # If verb appears before any subject → compound verb continuation (e.g., "comes and makes")
        if not found_subject and tok.pos_ in ("VERB", "AUX"):
            return False
        # Accept any noun/proper-noun/pronoun as a potential subject
        # (don't require nsubj — spaCy may label it 'conj' when bridging two clauses)
        if tok.pos_ in ("PROPN", "NOUN", "PRON"):
            found_subject = True
        # Verb found AFTER subject → this is an independent clause
        if found_subject and tok.pos_ in ("VERB", "AUX"):
            return True
    # Subject found but no verb → noun phrase coordination (e.g., "apples and oranges")
    return False

def analyze_connectors(doc, token):
    """
    Analyze whether a token is a connector that should trigger a sentence split.
    
    Processing logic and order:
     1. Check if the token is one of the target connectors based on the language.
     2. For 'that' (English), check if it's part of a contraction (e.g., that's, that'll).
     3. For all connectors, check if they function as a specific dependency of a verb or noun.
     4. Default to splitting for certain connectors if no other conditions are met.
     5. For coordinating conjunctions, check if they connect two independent clauses.
    """
    lang = doc.lang_
    if lang == "en":
        connectors = ["that", "which", "where", "when", "because", "but", "and", "or"]
        mark_dep = "mark"
        det_pron_deps = ["det", "pron"]
        verb_pos = "VERB"
        noun_pos = ["NOUN", "PROPN"]
    elif lang == "zh":
        connectors = ["因为", "所以", "但是", "而且", "虽然", "如果", "即使", "尽管"]
        mark_dep = "mark"
        det_pron_deps = ["det", "pron"]
        verb_pos = "VERB"
        noun_pos = ["NOUN", "PROPN"]
    elif lang == "ja":
        connectors = ["けれども", "しかし", "だから", "それで", "ので", "のに", "ため"]
        mark_dep = "mark"
        det_pron_deps = ["case"]
        verb_pos = "VERB"
        noun_pos = ["NOUN", "PROPN"]
    elif lang == "fr":
        connectors = ["que", "qui", "où", "quand", "parce que", "mais", "et", "ou"]
        mark_dep = "mark"
        det_pron_deps = ["det", "pron"]
        verb_pos = "VERB"
        noun_pos = ["NOUN", "PROPN"]
    elif lang == "ru":
        connectors = ["что", "который", "где", "когда", "потому что", "но", "и", "или"] 
        mark_dep = "mark"
        det_pron_deps = ["det"]
        verb_pos = "VERB"
        noun_pos = ["NOUN", "PROPN"]
    elif lang == "es":
        connectors = ["que", "cual", "donde", "cuando", "porque", "pero", "y", "o"]
        mark_dep = "mark"
        det_pron_deps = ["det", "pron"]
        verb_pos = "VERB"
        noun_pos = ["NOUN", "PROPN"]
    elif lang == "de":
        connectors = ["dass", "welche", "wo", "wann", "weil", "aber", "und", "oder"]
        mark_dep = "mark"
        det_pron_deps = ["det", "pron"]
        verb_pos = "VERB"
        noun_pos = ["NOUN", "PROPN"]
    elif lang == "it":
        connectors = ["che", "quale", "dove", "quando", "perché", "ma", "e", "o"]
        mark_dep = "mark"
        det_pron_deps = ["det", "pron"]
        verb_pos = "VERB"
        noun_pos = ["NOUN", "PROPN"]
    else:
        return False, False
    
    if token.text.lower() not in connectors:
        return False, False
    
    if lang == "en" and token.text.lower() == "that":
        if token.dep_ == mark_dep and token.head.pos_ == verb_pos:
            return True, False
        else:
            return False, False
    elif token.dep_ in det_pron_deps and token.head.pos_ in noun_pos:
        return False, False
    else:
        return True, _is_coordinating_conjunction(lang, token.text)

def split_by_connectors(text, context_words=5, nlp=None, min_right_words=3):
    doc = nlp(text)
    sentences = [doc.text]  # init
    
    while True:
        # Handle each task with a single cut
        # avoiding the fragmentation of a sentence into multiple parts at the same time.
        split_occurred = False
        new_sentences = []
        
        for sent in sentences:
            doc = nlp(sent)
            start = 0
            
            for i, token in enumerate(doc):
                split_before, is_coord = analyze_connectors(doc, token)
                
                if i + 1 < len(doc) and doc[i + 1].text in ["'s", "'re", "'ve", "'ll", "'d"]:
                    continue
                
                left_words = doc[max(0, token.i - context_words):token.i]
                right_words = doc[token.i+1:min(len(doc), token.i + context_words + 1)]
                
                left_words = [word.text for word in left_words if not word.is_punct]
                right_words = [word.text for word in right_words if not word.is_punct]
                
                if split_before:
                    # DEBUG: log every connector found
                    if token.text.lower() in ("and", "but", "or"):
                        coord_result = _right_side_starts_with_subject(doc, token.i) if is_coord else "N/A"
                        rprint(f"[dim]🔍 DEBUG connector '{token.text}' (i={token.i}): "
                               f"L={len(left_words)}/{context_words} R={len(right_words)}/{min_right_words} "
                               f"is_coord={is_coord} clause_check={coord_result}[/dim]")
                        rprint(f"[dim]🔍   TEXT: ...{doc[max(0,token.i-3):token.i].text}|{token.text}|{doc[token.i+1:min(len(doc),token.i+6)].text}...[/dim]")

                if len(left_words) >= context_words and len(right_words) >= min_right_words and split_before:
                    # For coordinating conjunctions, verify the right side is an independent clause
                    # (has a subject before any verb), not just a compound verb continuation
                    if is_coord and not _right_side_starts_with_subject(doc, token.i):
                        rprint(f"[dim]🔍 DEBUG: skipped split — right side not an independent clause[/dim]")
                        continue
                    rprint(f"[yellow]✂️  Split before '{token.text}': {' '.join(left_words)}| {token.text} {' '.join(right_words)}[/yellow]")
                    new_sentences.append(doc[start:token.i].text.strip())
                    start = token.i
                    split_occurred = True
                    break
            
            if start < len(doc):
                new_sentences.append(doc[start:].text.strip())
        
        if not split_occurred:
            break
        
        sentences = new_sentences
    
    return sentences

def split_sentences_main(nlp):
    # Read input sentences
    with open(SPLIT_BY_COMMA_FILE, "r", encoding="utf-8") as input_file:
        sentences = input_file.readlines()
    
    all_split_sentences = []
    # Process each input sentence
    for sentence in sentences:
        split_sentences = split_by_connectors(sentence.strip(), nlp = nlp)
        all_split_sentences.extend(split_sentences)
    
    with open(SPLIT_BY_CONNECTOR_FILE, "w+", encoding="utf-8") as output_file:
        for sentence in all_split_sentences:
            output_file.write(sentence + "\n")
        # do not add a newline at the end of the file
        output_file.seek(output_file.tell() - 1, os.SEEK_SET)
        output_file.truncate()

    # delete the original file
    os.remove(SPLIT_BY_COMMA_FILE)
    
    rprint(f"[green]💾 Sentences split by connectors saved to →  `{SPLIT_BY_CONNECTOR_FILE}`[/green]")

if __name__ == "__main__":
    nlp = init_nlp()
    split_sentences_main(nlp)
    # nlp = init_nlp()
    # a = "and show the specific differences that make a difference between a breakaway that results in a goal in the NHL versus one that doesn't."
    # print(split_by_connectors(a, nlp))