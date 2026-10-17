import json

from sec_10k_rag.common.common import with_progress
from sec_10k_rag.common.llm_config import ask_llm, get_llm
from sec_10k_rag.step_08_mcp_server.lib.config import (
    REPHRASED_QUESTION_PROMPT,
    AnswerInstructions,
    Turn,
)


def get_rephrased_question_with_history(
    question: str, instructions: AnswerInstructions, history: list[Turn] | None
) -> str:
    """Rephrase the question with the history of previous questions and answers.

    The history is a list of Turn objects, each containing a question and
    an answer. The LLM uses it to rewrite the current question as a
    standalone question.

    Args:
        question (str): The current question to be answered.
        history (list[Turn] | None): A list of previous questions and answers.

    Returns:
        str: The rephrased question string.
    """

    if not history:
        return question

    question_with_history = ""
    for turn in history:
        question_with_history += (
            f"Q: {turn['question']}\nA: {turn['answer']}\n\n"
        )
    question_with_history += (
        f"Current question: {question}\n"
        "Return rephrased question as "
        'JSON only: {"question": "..."}'
    )
    rephrased_question = with_progress(ask_llm)(
        get_llm(instructions.llm_info.max_retries),
        instructions.llm_info.model_name,
        instructions.llm_info.temperature,
        REPHRASED_QUESTION_PROMPT,
        f"{question_with_history}",
    )

    return str(json.loads(rephrased_question).get("question", question))
