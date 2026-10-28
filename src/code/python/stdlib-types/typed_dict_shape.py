"""TypedDict 描述一份字典的键。NotRequired 的键可以缺；Annotated 把额外说明留在类型上。"""

from typing import Annotated, NotRequired, TypedDict, get_args, get_origin, get_type_hints


class Job(TypedDict):
    name: str
    retries: NotRequired[int]


def retry_count(job: Job) -> int:
    return job.get("retries", 1)


class Payload(TypedDict):
    user_id: Annotated[str, "uuid"]


def annotation_label(spec: type) -> str:
    hints = get_type_hints(spec, include_extras=True)
    user_id = hints["user_id"]
    assert get_origin(user_id) is Annotated
    return get_args(user_id)[1]


if __name__ == "__main__":
    brief: Job = {"name": "index"}
    full: Job = {"name": "index", "retries": 3}
    assert retry_count(brief) == 1
    assert retry_count(full) == 3
    assert annotation_label(Payload) == "uuid"
    assert get_type_hints(Payload)["user_id"] is str
