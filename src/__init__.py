"""
This module contains the News-Check application components.
"""

import warnings

# Importing langchain_core triggers surface_langchain_deprecation_warnings(),
# which prepends "default" filters for LangChain*DeprecationWarning that
# would override a generic PendingDeprecationWarning filter. So we import
# the concrete class first, then filter it directly — this puts our
# "ignore" filter ahead of theirs in warnings.filters.
from langchain_core._api.deprecation import LangChainPendingDeprecationWarning

# langgraph instantiates langchain_core's Reviver without `allowed_objects`,
# emitting a PendingDeprecationWarning we cannot suppress at the call site.
warnings.filterwarnings(
    "ignore",
    message=r".*allowed_objects.*",
    category=LangChainPendingDeprecationWarning,
)

# langchain_openai stashes our `with_structured_output` parsed model into
# `AIMessage.additional_kwargs['parsed']`. When the message is later
# re-serialized by pydantic, the parsed BaseModel triggers
# PydanticSerializationUnexpectedValue. Behaviour is correct; warning is noise.
warnings.filterwarnings(
    "ignore",
    message=r"Pydantic serializer warnings:.*",
    category=UserWarning,
)
