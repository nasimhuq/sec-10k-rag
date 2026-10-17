from typing import Annotated

from mcp.server.mcpserver import MCPServer as mcp_server
from pydantic import Field

from sec_10k_rag.common.common import write_log
from sec_10k_rag.step_08_mcp_server.lib.answer import Answer, answer_question
from sec_10k_rag.step_08_mcp_server.lib.config import (
    LOG_FILE,
    Turn,
    get_answer_instructions,
)
from sec_10k_rag.step_08_mcp_server.lib.question import (
    get_rephrased_question_with_history,
)

ANSWER_INSTRUCTIONS = get_answer_instructions()

mcp = mcp_server("SEC 10-K RAG Server")


@mcp.tool()
def search(
    question: Annotated[
        str, Field(description="The user's question, as typed.")
    ],
    history: Annotated[
        list[Turn] | None,
        Field(
            description=(
                "Earlier questions and answers from this chat, oldest "
                "first. Answer text only, no citations. "
                "Empty on the first question. "
            )
        ),
    ] = None,
) -> Answer:
    """Answer a question about Tesla, Microsoft or Nvidia from their 10-Ks.

    Always pass the user's words unchanged in `question` and all
    earlier turns of this chat in `history`.
    Returns the answer and the 10-K sections it came from.
    """

    rephrased_question = get_rephrased_question_with_history(
        question, ANSWER_INSTRUCTIONS, history
    )

    write_log(
        LOG_FILE,
        {
            "question": question,
            "rephrased_question": (
                rephrased_question if rephrased_question != question else None
            ),
            "history": history,
        },
    )
    llm_reply = answer_question(rephrased_question, ANSWER_INSTRUCTIONS)

    write_log(LOG_FILE, {"answer": llm_reply.get("answer")})
    return llm_reply


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
