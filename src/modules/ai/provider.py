"""
Ollama Provider for EON.
"""

from __future__ import annotations

import threading

from ollama import Client

from src.core.logger import get_logger

logger = get_logger("AI.Provider")

#: How long Ollama keeps a model in memory after answering.
#:
#: On a small machine this is the most important number in the file.
#: Left unset, Ollama unloads the model after a few idle minutes and
#: the next call pays to read it back off disk â€” which, for a 2 GB
#: model on a drive with under a gigabyte free, is eleven to thirteen
#: seconds of doing nothing. Measured on EON: a ten-word reply took
#: 11s with nothing pinned, and about a second once it stayed resident.
#:
#: Long enough to survive a conversation; not so long that it sits in
#: memory after EON is closed.
DEFAULT_KEEP_ALIVE = "30m"

#: Generation options sent with every call.
#:
#: ``num_ctx`` matters most here: Ollama allocates the KV cache up
#: front from this number, and its default is larger than any prompt
#: EON builds. On 8 GB of RAM, that reserved memory is exactly what is
#: missing. ``num_predict`` stops a runaway reply, and ``temperature``
#: is pinned so the same question does not come back with a different
#: personality each time.
DEFAULT_OPTIONS: dict = {
    "num_ctx": 4096,
    "num_predict": 512,
    "temperature": 0.7,
}


class OllamaProvider:
    """
    Handles communication with Ollama.
    """

    def __init__(
        self,
        host: str = "http://127.0.0.1:11434",
        model: str = "qwen2.5:3b",
        embedding_model: str = "nomic-embed-text",
        keep_alive: str | int | None = None,
        options: dict | None = None,
    ) -> None:

        self.client = Client(host=host)

        self.model = model
        self.embedding_model = embedding_model

        # ``None`` means "use the defaults above", so an explicit empty
        # dict can still mean "send no options at all".
        self.keep_alive = (
            DEFAULT_KEEP_ALIVE if keep_alive is None else keep_alive
        )
        self.options = dict(DEFAULT_OPTIONS if options is None else options)

        # Logged because this is the difference between a one-second
        # reply and a twenty-second one, and it should be visible at
        # startup rather than inferred.
        logger.info(
            "Ollama Provider initialized (%s; keep_alive=%s, num_ctx=%s)",
            self.model,
            self.keep_alive,
            self.options.get("num_ctx"),
        )

    def chat(
        self,
        messages: list[dict],
    ) -> str:
        """
        Send a conversation to the language model.
        """

        response = self.client.chat(
            model=self.model,
            messages=messages,
            keep_alive=self.keep_alive,
            options=self.options,
        )

        return response["message"]["content"]

    def chat_stream(
        self,
        messages: list[dict],
    ):
        """
        Send a conversation to the language model, yielding the reply
        as incremental text deltas instead of waiting for it in full.
        """

        stream = self.client.chat(
            model=self.model,
            messages=messages,
            stream=True,
            keep_alive=self.keep_alive,
            options=self.options,
        )

        for chunk in stream:
            content = chunk["message"]["content"]

            if content:
                yield content

    def chat_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        model: str | None = None,
    ) -> str:
        """
        Send a single-turn prompt plus an image to a vision-capable
        model.

        Kept separate from ``chat`` rather than overloading it with an
        optional ``images`` param â€” this is deliberately single-turn
        (no conversation history) since vision queries in EON are
        always "here's what the screen looks like right now", not an
        ongoing multimodal conversation.

        Args:
            prompt: The question/instruction for the model.
            image_bytes: Encoded image data (e.g. JPEG bytes).
            model: Override the model to use for this call. Needed
                because ``self.model|` €¡Ñ¡”‘•™…Õ±Ð¡…Ðµ½‘•°°”¹œ¸(€€€€€€€€€€€€€€€ÅÝ•¸È¸ÔèÍ‰€¤¥ÌÙ•Éä±¥­•±ä¹½ÐÙ¥Í¥½¸µ…Á…‰±”ƒŠP(€€€€€€€€€€€€€€€…±±•ÉÌÍ¡½Õ±Á…ÍÌ„Ù¥Í¥½¸µ½‘•°ÍÕ …Ì€‰±±…Ù„‰€¸(€€€€€€€€ˆˆˆ((€€€€€€€É•ÍÁ½¹Í”€ôÍ•±˜¹±¥•¹Ð¹¡…Ð (€€€€€€€€€€€µ½‘•°õµ½‘•°½ÈÍ•±˜¹µ½‘•°°(€€€€€€€€€€€µ•ÍÍ…•Ìõl(€€€€€€€€€€€€€€€ì(€€€€€€€€€€€€€€€€€€€€‰É½±”ˆè€‰ÕÍ•Èˆ°(€€€€€€€€€€€€€€€€€€€€‰½¹Ñ•¹ÐˆèÁÉ½µÁÐ°(€€€€€€€€€€€€€€€€€€€€‰¥µ…•Ìˆèm¥µ…•}‰åÑ•Ít°(€€€€€€€€€€€€€€€ô(€€€€€€€€€€€t°(€€€€€€€€¤((€€€€€€€É•ÑÕÉ¸É•ÍÁ½¹Í•l‰µ•ÍÍ…”‰ul‰½¹Ñ•¹Ð‰t((€€€‘•˜•µ‰• (€€€€€€€Í•±˜°(€€€€€€€Ñ•áÐèÍÑÈ°(€€€€¤€´ø±¥ÍÑm™±½…Ñtè(€€€€€€€€ˆˆˆ(€€€€€€€•¹•É…Ñ”…¸•µ‰•‘‘¥¹œ™½ÈÑ•áÐ¸(€€€€€€€€ˆˆˆ((€€€€€€€É•ÍÁ½¹Í”€ôÍ•±˜¹±¥•¹Ð¹•µ‰• (€€€€€€€€€€€µ½‘•°õÍ•±˜¹•µ‰•‘‘¥¹}µ½‘•°°(€€€€€€€€€€€¥¹ÁÕÐõÑ•áÐ°(€€€€€€€€€€€­••Á}…±¥Ù”õÍ•±˜¹­••Á}…±¥Ù”°(€€€€€€€€¤((€€€€€€€É•ÑÕÉ¸É•ÍÁ½¹Í•l‰•µ‰•‘‘¥¹Ì‰ulÁt(((ŒQ¡”ÁÉ½Ù¥‘•È•Ù•Éä%5…¹…•ÈÍ¡…É•ÌÕ¹±•ÍÌ½¹”¥ÌÁ…ÍÍ•¥¸•áÁ±¥¥Ñ±ä¸)}‘•™…Õ±Ñ}ÁÉ½Ù¥‘•Èè€‰=±±…µ…AÉ½Ù¥‘•Èð9½¹”ˆ€ô9½¹”)}‘•™…Õ±Ñ}ÁÉ½Ù¥‘•É}±½¬€ôÑ¡É•…‘¥¹œ¹1½¬ ¤(()‘•˜•Ñ}‘•™…Õ±Ñ}ÁÉ½Ù¥‘•È ¤€´ø=±±…µ…AÉ½Ù¥‘•Èè(€€€€ˆˆ‰Q¡”Í¡…É•ÁÉ½Ù¥‘•È°É•…Ñ•½¹”½¸™¥ÉÍÐÕÍ”¸((€€€=±±…µ„Í•ÉÙ•Ì„Í¥¹±”½Áä½˜Ñ¡”µ½‘•°°…¹…¸=±±…µ…AÉ½Ù¥‘•É€(€€€¥Ì½¹±ä…¸!QQ@±¥•¹ÐÁ±ÕÌÑÝ¼µ½‘•°¹…µ•ÌƒŠPÍ¼„ÁÉ½Ù¥‘•È€©Á•È(€€€…±±•È¨‰ÕåÌ¹½Ñ¡¥¹œ¸%ÐÉ”µÉ•…‘ÌÑ¡”Í…µ”½¹™¥ÕÉ…Ñ¥½¸…¹½Á•¹Ì(€€€…¹½Ñ¡•È½¹¹•Ñ¥½¸Ñ¼Ñ¡”Í…µ”Í•ÉÙ•È¸=8‰Õ¥±‘ÌÍ•Ù•É…°€¡Ñ¡”(€€€‰É…¥¸°Ñ¡”µ•µ½ÉäÍÑ½É”°•µ‰•‘‘¥¹Ì°Ñ¡”Ù¥Í¥½¸…¹…±åÍ•È¤°Ý¡¥ (€€€Í¡½Ý•ÕÀ…Ì„ÉÕ¸½˜¥‘•¹Ñ¥…°€‰=±±…µ„AÉ½Ù¥‘•È¥¹¥Ñ¥…±¥é•ˆ(€€€±¥¹•Ì½¸•Ù•Éä±…Õ¹ ¸((€€€M¡…É¥¹œ¥ÌÍ…™”‰•…ÕÍ”Ñ¡”ÁÉ½Ù¥‘•È¡½±‘Ì¹¼½¹Ù•ÉÍ…Ñ¥½¸ÍÑ…Ñ”è(€€€•Ù•Éä…±°Á…ÍÍ•Ì¥ÑÌ½Ý¸µ•ÍÍ…•Ì¸((€€€I•ÑÕÉ¹Ìè(€€€€€€€Q¡”ÁÉ½•ÍÌµÝ¥‘”ÁÉ½Ù¥‘•È¸(€€€€ˆˆˆ(€€€±½‰…°}‘•™…Õ±Ñ}ÁÉ½Ù¥‘•È((€€€¥˜}‘•™…Õ±Ñ}ÁÉ½Ù¥‘•È¥Ì9½¹”è(€€€€€€€Ý¥Ñ }‘•™…Õ±Ñ}ÁÉ½Ù¥‘•É}±½¬è(€€€€€€€€€€€€ŒI”µ¡•¬¥¹Í¥‘”Ñ¡”±½¬èÑÝ¼Ñ¡É•…‘Ì…¸‰½Ñ •ÐÁ…ÍÐ(€€€€€€€€€€€€ŒÑ¡”¡•¬…‰½Ù”‰•™½É”•¥Ñ¡•ÈÑ…­•ÌÑ¡”±½¬¸(€€€€€€€€€€€¥˜}‘•™…Õ±Ñ}ÁÉ½Ù¥‘•È¥Ì9½¹”è(€€€€€€€€€€€€€€€}‘•™…Õ±Ñ}ÁÉ½Ù¥‘•È€ô=±±…µ…AÉ½Ù¥‘•È ¤((€€€É•ÑÕÉ¸}‘•™…Õ±Ñ}ÁÉ½Ù¥‘•È(