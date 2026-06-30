from __future__ import annotations

from collections import deque
from dataclasses import dataclass


GRID_SIZE = 8


@dataclass(frozen=True)
class TrialConfiguration:
    description: str
    test_type: int
    bombs_raw: str
    start_raw: str
    stop_raw: str
    bombs: frozenset[tuple[int, int]]
    start: tuple[int, int] | None
    stop: tuple[int, int] | None
    minimum_moves: int | None
    minimum_intermediate_cells: int | None
    minimum_path: tuple[str, ...]


def clean(value) -> str:
    return str(value or "").strip()


def parse_coordinate(value: str) -> tuple[int, int]:
    text = clean(value).upper()
    if len(text) != 2 or text[0] not in "ABCDEFGH" or text[1] not in "12345678":
        raise ValueError(f"Invalid Minefield coordinate: {value!r}")
    return ord(text[0]) - ord("A"), int(text[1]) - 1


def format_coordinate(coordinate: tuple[int, int]) -> str:
    x, y = coordinate
    return f"{chr(ord('A') + x)}{y + 1}"


def parse_coordinate_list(value: str) -> frozenset[tuple[int, int]]:
    tokens = [token.strip() for token in clean(value).upper().split("-") if token.strip()]
    return frozenset(parse_coordinate(token) for token in tokens)


def shortest_path(
    start: tuple[int, int],
    stop: tuple[int, int],
    blocked: frozenset[tuple[int, int]] | set[tuple[int, int]],
) -> tuple[tuple[int, int], ...] | None:
    if start in blocked or stop in blocked:
        return None

    queue = deque([start])
    previous: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    while queue:
        current = queue.popleft()
        if current == stop:
            path = []
            cursor: tuple[int, int] | None = current
            while cursor is not None:
                path.append(cursor)
                cursor = previous[cursor]
            return tuple(reversed(path))

        x, y = current
        for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            nx, ny = neighbor
            if not (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE):
                continue
            if neighbor in blocked or neighbor in previous:
                continue
            previous[neighbor] = current
            queue.append(neighbor)
    return None


def build_trial_configuration(
    description,
    test_type,
    bombs,
    start,
    stop,
) -> TrialConfiguration:
    description_text = clean(description).upper()
    bombs_text = clean(bombs).upper()
    start_text = clean(start).upper()
    stop_text = clean(stop).upper()
    parsed_bombs = parse_coordinate_list(bombs_text)

    # Working Memory has no spatial route; its configuration contains only
    # the target coordinates used by the memory task.
    if not start_text or not stop_text:
        return TrialConfiguration(
            description=description_text,
            test_type=int(test_type),
            bombs_raw=bombs_text,
            start_raw=start_text,
            stop_raw=stop_text,
            bombs=parsed_bombs,
            start=None,
            stop=None,
            minimum_moves=None,
            minimum_intermediate_cells=None,
            minimum_path=(),
        )

    parsed_start = parse_coordinate(start_text)
    parsed_stop = parse_coordinate(stop_text)
    path = shortest_path(parsed_start, parsed_stop, parsed_bombs)
    if path is None:
        minimum_moves = None
        minimum_cells = None
        path_text: tuple[str, ...] = ()
    else:
        minimum_moves = len(path) - 1
        minimum_cells = max(minimum_moves - 1, 0)
        path_text = tuple(format_coordinate(coordinate) for coordinate in path)

    return TrialConfiguration(
        description=description_text,
        test_type=int(test_type),
        bombs_raw=bombs_text,
        start_raw=start_text,
        stop_raw=stop_text,
        bombs=parsed_bombs,
        start=parsed_start,
        stop=parsed_stop,
        minimum_moves=minimum_moves,
        minimum_intermediate_cells=minimum_cells,
        minimum_path=path_text,
    )
