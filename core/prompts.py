import json
from core.utils import *

## ================================================================
# @ step4_splitbymeaning.py
def get_split_prompt(sentence, num_parts = 2, word_limit = 20):
    language = load_key("whisper.detected_language")
    split_prompt = f"""
## Role
You are a professional Netflix subtitle splitter in **{language}**.

## Task
Split the given subtitle text into **{num_parts}** parts, each less than **{word_limit}** words.

1. Maintain sentence meaning coherence according to Netflix subtitle standards
2. MOST IMPORTANT: Keep parts roughly equal in length (minimum 3 words each)
3. Split at natural points like punctuation marks or conjunctions
4. CRITICAL: NEVER split a number (e.g., "1,500", "1,000", "5'9"", "200-pound"). Keep all parts of a number together in one segment. Do NOT place [br] inside or adjacent to numbers.
5. If provided text is repeated words, simply split at the middle of the repeated words.

## Steps
1. Analyze the sentence structure, complexity, and key splitting challenges
2. Generate two alternative splitting approaches with [br] tags at split positions
3. Compare both approaches highlighting their strengths and weaknesses
4. Choose the best splitting approach

## Given Text
<split_this_sentence>
{sentence}
</split_this_sentence>

## Output in only JSON format and no other text
```json
{{
    "analysis": "Brief description of sentence structure, complexity, and key splitting challenges",
    "split1": "First splitting approach with [br] tags at split positions",
    "split2": "Alternative splitting approach with [br] tags at split positions",
    "assess": "Comparison of both approaches highlighting their strengths and weaknesses",
    "choice": "1 or 2"
}}
```

Note: Start you answer with ```json and end with ```, do not add any other text.
""".strip()
    return split_prompt

"""{{
    "analysis": "Brief analysis of the text structure",
    "split": "Complete sentence with [br] tags at split positions"
}}"""

## ================================================================
# @ step4_1_summarize.py
def get_summary_prompt(source_content, custom_terms_json=None, video_description=None):
    src_lang = load_key("whisper.detected_language")
    tgt_lang = load_key("target_language")
    
    # add custom terms note
    terms_note = ""
    if custom_terms_json:
        terms_list = []
        for term in custom_terms_json['terms']:
            terms_list.append(f"- {term['src']}: {term['tgt']} ({term['note']})")
        terms_note = "\n### Existing Terms\nPlease exclude these terms in your extraction:\n" + "\n".join(terms_list)

    video_description_note = ""
    if video_description:
        video_description_note = f"""
### Video Description
Use this creator-provided video description as background context for topic, names, terminology, and intended meaning. Do not translate the description itself unless relevant terms appear in the subtitles.
Pay special attention to proper nouns in the description. WhisperX may misspell names, titles, teams, brands, or places in the subtitle transcript. Extract these proper nouns as terms and note that similar ASR spellings should be normalized to the exact description spelling.
<video_description>
{video_description}
</video_description>
""".strip()
    
    summary_prompt = f"""
## Role
You are a video translation expert and terminology consultant, specializing in {src_lang} comprehension and {tgt_lang} expression optimization.

## Task
For the provided {src_lang} video text:
1. Summarize main topic in two sentences
2. Extract professional terms/names with {tgt_lang} translations (excluding existing terms)
3. Provide brief explanation for each term

{terms_note}

{video_description_note}

Steps:
1. Topic Summary:
   - Quick scan for general understanding
   - Write two sentences: first for main topic, second for key point
2. Term Extraction:
   - Mark professional terms and names (excluding those listed in Existing Terms)
   - Include important proper nouns from the video description even if the transcript spelling is slightly different
   - Provide {tgt_lang} translation or keep original
   - Add brief explanation
   - Extract less than 15 terms

## INPUT
<text>
{source_content}
</text>

## Output in only JSON format and no other text
{{
  "theme": "Two-sentence video summary",
  "terms": [
    {{
      "src": "{src_lang} term",
      "tgt": "{tgt_lang} translation or original", 
      "note": "Brief explanation"
    }},
    ...
  ]
}}  

## Example
{{
  "theme": "本视频介绍人工智能在医疗领域的应用现状。重点展示了AI在医学影像诊断和药物研发中的突破性进展。",
  "terms": [
    {{
      "src": "Machine Learning",
      "tgt": "机器学习",
      "note": "AI的核心技术，通过数据训练实现智能决策"
    }},
    {{
      "src": "CNN",
      "tgt": "CNN",
      "note": "卷积神经网络，用于医学图像识别的深度学习模型"
    }}
  ]
}}

Note: Start you answer with ```json and end with ```, do not add any other text.
""".strip()
    return summary_prompt

## ================================================================
# @ step5_translate.py & translate_lines.py
def generate_shared_prompt(previous_content_prompt, after_content_prompt, summary_prompt, things_to_note_prompt):
    return f'''### Context Information
<previous_content>
{previous_content_prompt}
</previous_content>

<subsequent_content>
{after_content_prompt}
</subsequent_content>

### Content Summary
{summary_prompt}

### Points to Note
{things_to_note_prompt}'''

def get_prompt_faithfulness(lines, shared_prompt):
    TARGET_LANGUAGE = load_key("target_language")
    # Split lines by \n
    line_splits = lines.split('\n')
    
    json_dict = {}
    for i, line in enumerate(line_splits, 1):
        json_dict[f"{i}"] = {"origin": line, "direct": f"direct {TARGET_LANGUAGE} translation {i}."}
    json_format = json.dumps(json_dict, indent=2, ensure_ascii=False)

    src_language = load_key("whisper.detected_language")
    prompt_faithfulness = f'''
## Role
You are a professional Netflix subtitle translator, fluent in both {src_language} and {TARGET_LANGUAGE}, as well as their respective cultures. 
Your expertise lies in accurately understanding the semantics and structure of the original {src_language} text and faithfully translating it into {TARGET_LANGUAGE} while preserving the original meaning.

## Task
We have a segment of original {src_language} subtitles that need to be directly translated into {TARGET_LANGUAGE}. These subtitles come from a specific context and may contain specific themes and terminology.

1. Translate the original {src_language} subtitles into {TARGET_LANGUAGE} line by line
2. Ensure the translation is faithful to the original, accurately conveying the original meaning
3. Consider the context and professional terminology

{shared_prompt}

<translation_principles>
1. Faithful to the original: Accurately convey the content and meaning of the original text, without arbitrarily changing, adding, or omitting content.
2. Accurate terminology: Use professional terms correctly and maintain consistency in terminology.
3. Understand the context: Fully comprehend and reflect the background and contextual relationships of the text.
4. Keep common English acronyms such as NBA, AI, DNA, MBA, CEO, FBI, and NASA as acronyms by default; do not expand or translate them unless the local context or terminology notes specifically require it.
5. When Chinese text contains English words, acronyms, brand names, product names, or numbers, put a space between the Chinese characters and the English/number text, e.g. "工作流模型 API 密钥有效", "iPhone 手机", "AI 技术".
</translation_principles>

## INPUT
<subtitles>
{lines}
</subtitles>

## Output in only JSON format and no other text
```json
{json_format}
```

Note: Start you answer with ```json and end with ```, do not add any other text.
'''
    return prompt_faithfulness.strip()


def get_prompt_expressiveness(faithfulness_result, lines, shared_prompt):
    TARGET_LANGUAGE = load_key("target_language")
    json_format = {
        key: {
            "origin": value["origin"],
            "direct": value["direct"],
            "reflect": "your reflection on direct translation",
            "free": "your free translation",
            "ambiguous": False,
            "ambiguity": "ambiguous word or phrase, or empty string if none",
            "reason": "why this should be manually checked, or empty string if none"
        }
        for key, value in faithfulness_result.items()
    }
    json_format = json.dumps(json_format, indent=2, ensure_ascii=False)

    src_language = load_key("whisper.detected_language")
    prompt_expressiveness = f'''
## Role
You are a professional Netflix subtitle translator and language consultant.
Your expertise lies not only in accurately understanding the original {src_language} but also in optimizing the {TARGET_LANGUAGE} translation to better suit the target language's expression habits and cultural background.

## Task
We already have a direct translation version of the original {src_language} subtitles.
Your task is to reflect on and improve these direct translations to create more natural and fluent {TARGET_LANGUAGE} subtitles.

1. Analyze the direct translation results line by line, pointing out existing issues
2. Provide detailed modification suggestions
3. Perform free translation based on your analysis
4. Do not add comments or explanations in the translation, as the subtitles are for the audience to read
5. Do not leave empty lines in the free translation, as the subtitles are for the audience to read
6. If a source word or phrase could reasonably have multiple meanings, set "ambiguous" to true even when context resolves it. Fill "ambiguity" with the exact word/phrase and "reason" with a concise manual-check note.
7. Correct likely ASR misspellings of proper nouns by using the exact name/title/place/team/brand from the video description or terminology notes when context supports it.

{shared_prompt}

<Translation Analysis Steps>
Please use a two-step thinking process to handle the text line by line:

1. Direct Translation Reflection:
   - Evaluate language fluency
   - Check if the language style is consistent with the original text
   - Check the conciseness of the subtitles, point out where the translation is too wordy

2. {TARGET_LANGUAGE} Free Translation:
   - Aim for contextual smoothness and naturalness, conforming to {TARGET_LANGUAGE} expression habits
   - Ensure it's easy for {TARGET_LANGUAGE} audience to understand and accept
   - Adapt the language style to match the theme (e.g., use casual language for tutorials, professional terminology for technical content, formal language for documentaries)
   - Use the video description, summary, surrounding context, and terminology notes to resolve ambiguous words, but still flag ambiguous words for manual review
   - If a name in the subtitle looks like a misspelling of a proper noun from the video description, use the exact description spelling in the free translation
   - Keep common English acronyms such as NBA, AI, DNA, MBA, CEO, FBI, and NASA as acronyms by default; do not expand or translate them unless the local context or terminology notes specifically require it
   - When Chinese text contains English words, acronyms, brand names, product names, or numbers, put a space between the Chinese characters and the English/number text, e.g. "工作流模型 API 密钥有效", "iPhone 手机", "AI 技术"
</Translation Analysis Steps>
   
## INPUT
<subtitles>
{lines}
</subtitles>

## Output in only JSON format and no other text
```json
{json_format}
```

Note: Start you answer with ```json and end with ```, do not add any other text.
'''
    return prompt_expressiveness.strip()

def get_prompt_refine_translator_result(lines, translations, shared_prompt):
    TARGET_LANGUAGE = load_key("target_language")
    src_language = load_key("whisper.detected_language")
    source_lines = lines.split('\n')
    translation_lines = translations.split('\n')
    json_format = {
        str(i): {
            "origin": source,
            "direct": translation_lines[i - 1] if i - 1 < len(translation_lines) else "",
            "reflect": "brief reflection on problems in direct translation",
            "free": f"natural concise {TARGET_LANGUAGE} subtitle",
            "ambiguous": False,
            "ambiguity": "ambiguous word or phrase, or empty string if none",
            "reason": "why this should be manually checked, or empty string if none"
        }
        for i, source in enumerate(source_lines, 1)
    }
    json_format = json.dumps(json_format, indent=2, ensure_ascii=False)

    return f'''
## Role
You are a senior Netflix subtitle translation editor fluent in {src_language} and {TARGET_LANGUAGE}.

## Task
The plain translation model has produced direct {TARGET_LANGUAGE} translations.
Reflect on each direct translation and rewrite it into a natural, concise, viewer-friendly free translation.

Rules:
1. Preserve the source meaning and terminology.
2. Use idiomatic {TARGET_LANGUAGE}, not word-for-word machine translation.
3. Remove meaningless spoken fillers such as um, uh, er, hmm when they do not carry meaning.
4. Keep names, titles, and proper nouns accurate.
5. Use the video description, summary, surrounding context, and terminology notes to resolve ambiguous words. For example, if the video is about filmmaking or an interview about making a film, translate "shoot" / "shooting" as filming/拍摄 rather than weapon shooting/射击 unless the local sentence clearly means weapons.
6. Correct likely ASR misspellings of proper nouns by using the exact name/title/place/team/brand from the video description or terminology notes when context supports it. For example, if the description mentions "Gout Gout" but ASR says "Gaut", "Gao", or "Gout", use "Gout Gout".
7. Treat a standalone English lowercase "i" as the first-person pronoun "I" unless the local context clearly means a letter or symbol.
8. If a source word or phrase could reasonably have multiple meanings, set "ambiguous" to true even when you believe the context resolves it. Fill "ambiguity" with the specific word/phrase and "reason" with a concise manual-check note.
9. Keep common English acronyms such as NBA, AI, DNA, MBA, CEO, FBI, and NASA as acronyms by default; do not expand or translate them unless the local context or terminology notes specifically require it.
10. When Chinese text contains English words, acronyms, brand names, product names, or numbers, put a space between the Chinese characters and the English/number text, e.g. "工作流模型 API 密钥有效", "iPhone 手机", "AI 技术".
11. Keep exactly the same item keys and one free translation per source line.
12. Do not output comments outside JSON.

{shared_prompt}

## INPUT
<subtitles>
{lines}
</subtitles>

<direct_translations>
{translations}
</direct_translations>

## Output in only JSON format and no other text
```json
{json_format}
```

Note: Start your answer with ```json and end with ```, do not add any other text.
'''.strip()


## ================================================================
# @ step6_splitforsub.py
def get_align_prompt(src_sub, tr_sub, src_part):
    targ_lang = load_key("target_language")
    src_lang = load_key("whisper.detected_language")
    src_splits = src_part.split('\n')
    num_parts = len(src_splits)
    src_part = src_part.replace('\n', ' [br] ')
    align_parts_json = ','.join(
        f'''
        {{
            "src_part_{i+1}": "{src_splits[i]}",
            "target_part_{i+1}": "Corresponding aligned {targ_lang} subtitle part"
        }}''' for i in range(num_parts)
    )

    align_prompt = f'''
## Role
You are a Netflix subtitle alignment expert fluent in both {src_lang} and {targ_lang}.

## Task
We have {src_lang} and {targ_lang} original subtitles for a Netflix program, as well as a pre-processed split version of {src_lang} subtitles.
Your task is to create the best splitting scheme for the {targ_lang} subtitles based on this information.

1. Analyze the word order and structural correspondence between {src_lang} and {targ_lang} subtitles
2. Split the {targ_lang} subtitles according to the pre-processed {src_lang} split version
3. Use free translation when needed: the aligned {targ_lang} parts should be natural subtitles, not rigid word-for-word fragments
4. Remove meaningless spoken fillers such as um, uh, er, hmm when they do not carry meaning
5. Never leave empty lines. If it's difficult to split based on meaning, you may appropriately rewrite the sentences that need to be aligned
6. Keep each target part semantically matched to its corresponding source part; do not move content to the wrong line
7. Do not add comments or explanations in the translation, as the subtitles are for the audience to read
8. Keep common English acronyms such as NBA, AI, DNA, MBA, CEO, FBI, and NASA as acronyms by default; do not expand or translate them unless the local context or terminology notes specifically require it.
9. When Chinese text contains English words, acronyms, brand names, product names, or numbers, put a space between the Chinese characters and the English/number text, e.g. "工作流模型 API 密钥有效", "iPhone 手机", "AI 技术".

## INPUT
<subtitles>
{src_lang} Original: "{src_sub}"
{targ_lang} Original: "{tr_sub}"
Pre-processed {src_lang} Subtitles ([br] indicates split points): {src_part}
</subtitles>

## Output in only JSON format and no other text
```json
{{
    "analysis": "Brief analysis of word order, structure, and semantic correspondence between two subtitles",
    "align": [
        {align_parts_json}
    ]
}}
```

Note: Start you answer with ```json and end with ```, do not add any other text.
'''.strip()
    return align_prompt

## ================================================================
# @ step8_gen_audio_task.py @ step10_gen_audio.py
def get_subtitle_trim_prompt(text, duration):
 
    rule = '''Consider a. Reducing filler words without modifying meaningful content. b. Omitting unnecessary modifiers or pronouns, for example:
    - "Please explain your thought process" can be shortened to "Please explain thought process"
    - "We need to carefully analyze this complex problem" can be shortened to "We need to analyze this problem"
    - "Let's discuss the various different perspectives on this topic" can be shortened to "Let's discuss different perspectives on this topic"
    - "Can you describe in detail your experience from yesterday" can be shortened to "Can you describe yesterday's experience" '''

    trim_prompt = f'''
## Role
You are a professional subtitle editor, editing and optimizing lengthy subtitles that exceed voiceover time before handing them to voice actors. 
Your expertise lies in cleverly shortening subtitles slightly while ensuring the original meaning and structure remain unchanged.

## INPUT
<subtitles>
Subtitle: "{text}"
Duration: {duration} seconds
</subtitles>

## Processing Rules
{rule}

## Processing Steps
Please follow these steps and provide the results in the JSON output:
1. Analysis: Briefly analyze the subtitle's structure, key information, and filler words that can be omitted.
2. Trimming: Based on the rules and analysis, optimize the subtitle by making it more concise according to the processing rules.

## Output in only JSON format and no other text
```json
{{
    "analysis": "Brief analysis of the subtitle, including structure, key information, and potential processing locations",
    "result": "Optimized and shortened subtitle in the original subtitle language"
}}
```

Note: Start you answer with ```json and end with ```, do not add any other text.
'''.strip()
    return trim_prompt

## ================================================================
# @ tts_main
def get_correct_text_prompt(text):
    return f'''
## Role
You are a text cleaning expert for TTS (Text-to-Speech) systems.

## Task
Clean the given text by:
1. Keep only basic punctuation (.,?!)
2. Preserve the original meaning

## INPUT
{text}

## Output in only JSON format and no other text
```json
{{
    "text": "cleaned text here"
}}
```

Note: Start you answer with ```json and end with ```, do not add any other text.
'''.strip()
