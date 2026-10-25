"""The harness's task types (Brain, 0.8.0 stage 09): each is a family of problems from Kurooto's own life with a code
grader.

A task type has `make(rng)` (one instance: the inputs the policy sees and the key only the grader sees),
`grade(answer, key)`
(a score from 0 to 1, in plain code) and `solve(inputs)` (what the built-in rules policy answers: the baseline). New
instances
come from templates, so a rotation gives new problems and old ones can't be memorised.
"""

from kurooto.mind.harness.tasks.library import FAMILIES, TASK_TYPES, TaskType

__all__ = ["FAMILIES", "TASK_TYPES", "TaskType"]
