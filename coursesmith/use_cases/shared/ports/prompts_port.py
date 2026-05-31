from abc import ABC, abstractmethod


class PromptsPort(ABC):
    @abstractmethod
    def get_prompt(self, name: str, version: int) -> str:
        pass
