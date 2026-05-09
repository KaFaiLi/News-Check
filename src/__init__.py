"""
This module contains the News-Check application components.
"""

import warnings

# langchain_openai stashes our `with_structured_output` parsed model into
# `AIMessage.additional_kwargs['parsed']`. When the message is later
# re-serialized by pydantic, the parsed BaseModel triggers
# PydanticSerializationUnexpectedValue. Behaviour is correct; warning is noise.
warnings.filterwarnings(
    "ignore",
    message=r"Pydantic serializer warnings:.*",
    category=UserWarning,
)
