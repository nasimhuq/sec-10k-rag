from dataclasses import dataclass, field
from typing import TypedDict

from sec_10k_rag.common.config import ROOT_DIR
from sec_10k_rag.common.db_config import (
    PG_TABLE,
    DbConnInfo,
    get_db_conn_info,
)
from sec_10k_rag.step_07_search_quality.config import (
    LLM_MODEL_NAME,
    LlmInfo,
    ScoreSearchInstructions,
)

ANSWER_PROMPT = """Answer the question using only the numbered passages below.
If the passages do not contain the answer, say so.
Return JSON only: {"answer": "...", "sources": [passage numbers used]}"""
NO_ANSWER = "The LLM returned no answer."
LOG_FILE = ROOT_DIR / "mcp_server.log"

REPHRASED_QUESTION_PROMPT = """Rephrase the current question as a standalone
question, using the earlier questions and answers for context.
Do not add facts from earlier answers.
Previous questions and answers:"""


class Turn(TypedDict):
    question: str
    answer: str


@dataclass(frozen=True, kw_only=True)
class AnswerInstructions:
    db: DbConnInfo
    search: ScoreSearchInstructions
    llm_info: LlmInfo = field(
        default_factory=lambda: LlmInfo(
            model_name=LLM_MODEL_NAME, temperature=0.0
        )
    )
    chunks_table: str = PG_TABLE
    prompt: str = ANSWER_PROMPT


def get_answer_instructions() -> AnswerInstructions:
    db = get_db_conn_info()
    return AnswerInstructions(
        db=db, search=ScoreSearchInstructions(db=db, top_k=5)
    )
