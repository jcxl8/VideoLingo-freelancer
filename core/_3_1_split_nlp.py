from core.spacy_utils import *
from core.spacy_utils.merge_short_segments import merge_short_segments_main
from core.spacy_utils.source_quality import postprocess_source_segments_file
from core.utils.models import _3_1_SPLIT_BY_NLP


def split_by_spacy():
    nlp = init_nlp()
    split_by_mark(nlp)
    split_by_comma_main(nlp)
    split_sentences_main(nlp)
    split_long_by_root_main(nlp)

    # 新增：基础 NLP 断句后，合并过短碎片
    merge_short_segments_main()
    postprocess_source_segments_file(_3_1_SPLIT_BY_NLP)

    return


if __name__ == '__main__':
    split_by_spacy()
