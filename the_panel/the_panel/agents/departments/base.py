"""Shared shell for every department (P8). Each department supplies its brief text and output model."""
from __future__ import annotations

from typing import Any, ClassVar

from ...schemas.common import Department
from ...schemas.directive import DEPARTMENT_OUTPUTS, DepartmentDirective, DepartmentOutput
from ..base import BaseAgent


class DepartmentAgent(BaseAgent[DepartmentOutput]):
    stage = "department"
    template = "P8_department"
    dept: ClassVar[Department]

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        if hasattr(cls, "dept"):
            cls.output_model = DEPARTMENT_OUTPUTS[cls.dept]
            cls.name = f"dept_{cls.dept.value}"

    def brief(self) -> str:
        """The department-specific P8.x brief (rendered into the shared shell as ``dept_brief``)."""
        raise NotImplementedError

    def check(self, parsed: DepartmentOutput, variables: dict[str, Any]) -> None:
        raise NotImplementedError("CP-6: must_not includes the Style Bible refusals touching this dept; no re-decision of governing idea")

    def wrap(self, output: DepartmentOutput, plan: Any) -> DepartmentDirective:
        """Governing idea and pleasure beat are copied from the plan — departments cannot alter them."""
        return DepartmentDirective.from_output(self.dept, plan.scene_id, plan.governing_idea, plan.pleasure_beat, output)


def department_agent_for(dept: Department) -> type[DepartmentAgent]:
    raise NotImplementedError("CP-6: map Department → agent class")
