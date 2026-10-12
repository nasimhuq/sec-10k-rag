from sec_10k_rag.common.common import write_to_parquet_file
from sec_10k_rag.step_05_embedding.config import ConfigType, get_config
from sec_10k_rag.step_05_embedding.load import load_chunks
from sec_10k_rag.step_05_embedding.report import report_results
from sec_10k_rag.step_05_embedding.tokenize import tokenize
from sec_10k_rag.step_05_embedding.vectorize import vectorize


def main() -> None:
    chunks_df = load_chunks(get_config(ConfigType.LOAD_CHUNKS), "chunks.parquet")
    tokenized_data = tokenize(get_config(ConfigType.TOKENIZE), chunks_df)
    report_results(tokenized_data)
    vectorized_config = get_config(ConfigType.VECTORIZE)
    embedded_df = vectorize(vectorized_config, chunks_df)
    output_file = vectorized_config.processed_data_dir / "chunks_embedded.parquet"
    write_to_parquet_file(embedded_df, output_file)


if __name__ == "__main__":
    main()
