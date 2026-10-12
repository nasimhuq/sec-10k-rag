import sys
from collections.abc import Callable
from pathlib import Path

from sec_10k_rag.common.common import (
    start_db,
    with_progress,
    write_to_parquet_file,
)
from sec_10k_rag.step_07_search_quality.config import (
    ConfigType,
    GenerateQuestionsInstructions,
    ScoreSearchInstructions,
    get_config,
)
from sec_10k_rag.step_07_search_quality.lib import (
    find_nearest_neighbors,
    generate_questions,
    get_question_vectors,
    load_chunks_text_from_db,
    rank_of_source,
    sample_chunks,
    score,
)


@with_progress
def run_score_search() -> Path:
    config = get_config(ConfigType.SCORE_SEARCH)
    ins = config.instructions
    if not isinstance(ins, ScoreSearchInstructions):
        raise TypeError("expected ScoreSearchInstructions")

    questions_path = Path(config.processed_data_dir) / ins.input_file_name
    return questions_path


@with_progress
def run_generate_questions() -> Path:
    config = get_config(ConfigType.GENERATE_QUESTIONS)
    instructions = config.instructions
    if not isinstance(instructions, GenerateQuestionsInstructions):
        raise TypeError("expected GenerateQuestionsInstructions")

    chunks = with_progress(load_chunks_text_from_db)(
        instructions.db, instructions.chunks_table
    )  # chunks.parquet
    sample = with_progress(sample_chunks)(
        chunks,
        n=instructions.sample_size,
        seed=instructions.seed,
    )

    questions = with_progress(generate_questions)(
        sample=sample,
        llm_info=instructions.llm_info,
        company_names=instructions.company_names,
    )  # keeps section_id, chunk_index
    questions_path = (
        Path(config.processed_data_dir) / instructions.output_file_name
    )
    with_progress(write_to_parquet_file)(questions, questions_path)
    return questions_path


RUNNERS: dict[ConfigType, Callable[[], Path]] = {
    ConfigType.GENERATE_QUESTIONS: run_generate_questions,
    ConfigType.SCORE_SEARCH: run_score_search,
}


def main() -> None:
    print("Running search quality checks...")
    with_progress(start_db)()
    name = sys.argv[1] if len(sys.argv) > 1 else ConfigType.GENERATE_QUESTIONS
    questions_path = RUNNERS[ConfigType(name)]()

    question_vector_df = with_progress(get_question_vectors)(questions_path)
    config = get_config(ConfigType.SCORE_SEARCH)
    instructions = config.instructions
    if not isinstance(instructions, ScoreSearchInstructions):
        raise TypeError("expected ScoreSearchInstructions")

    nearest_neighbors = with_progress(find_nearest_neighbors)(
        question_vector_df,
        db=instructions.db,
        table=instructions.chunks_table,
        top_k=10,
    )

    ranks = with_progress(rank_of_source)(question_vector_df, nearest_neighbors)
    with_progress(write_to_parquet_file)(
        ranks, Path(config.processed_data_dir) / instructions.output_file_name
    )
    print(with_progress(score)(ranks, instructions.recall_ks))


if __name__ == "__main__":
    main()
