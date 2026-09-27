import re
from typing import Any

import yaml


class _Yaml12Loader(yaml.SafeLoader):
    """SafeLoader with YAML 1.2 booleans: only true/false, never on/off/yes/no.

    Scenario files use ``on: agent_turn``; under YAML 1.1 rules the key ``on``
    silently becomes the boolean True.
    """


_Yaml12Loader.yaml_implicit_resolvers = {
    first: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:bool"]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Yaml12Loader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
)


def load_yaml(text: str) -> Any:
    """Parse YAML text safely with YAML 1.2 boolean semantics."""
    return yaml.load(text, Loader=_Yaml12Loader)
