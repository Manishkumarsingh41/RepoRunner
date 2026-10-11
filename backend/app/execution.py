from typing import Protocol


class ExecutionProvider(Protocol):
    def start(self, job_id: str, commands: list[str]) -> None: ...
    def stop(self, job_id: str) -> None: ...


class UnavailableExecutionProvider:
    reason = "Execution unavailable: no verified isolated execution provider is configured"

    def start(self, job_id: str, commands: list[str]) -> None:
        raise RuntimeError(self.reason)

    def stop(self, job_id: str) -> None:
        return None


provider = UnavailableExecutionProvider()
