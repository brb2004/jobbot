"""Which job titles a user sees: engineering roles by default, minus sales, support and hardware roles."""

from app.core.words_core import has_any

DEFAULT_TITLES = ("engineer", "developer", "sre", "devops", "architect", "programmer", "scientist")
# Sales roles, not any title that mentions sales: "Software Engineer, Sales Platform" builds software.
PRESALES_TITLES = tuple(
    "sales engineer, sales engineering, sales architect, sales consultant, sales representative, "
    "sales development, sales executive, sales manager, sales specialist, presales, pre-sales, "
    "customer engineer, solutions architect, solution architect, solutions engineer, solution engineer, "
    "account executive, customer success".split(", ")
)
# Shown only when the user names one of these phrases; a generic "engineer" doesn't bring them back.
NON_DEV_TITLES = tuple(
    "support engineer, technical support, customer support, curriculum, creative engineer, "
    "enterprise engineer, help desk, helpdesk".split(", ")
)
HARDWARE_TITLES = tuple(
    "hardware engineer, hardware design, electrical engineer, mechanical engineer, asic, fpga, rtl, pcb, "
    "analog, mixed-signal, silicon, physical design, design verification, rf engineer, manufacturing engineer, "
    "process engineer, chemical engineer, civil engineer, structural engineer, optical engineer, "
    "thermal engineer, packaging engineer".split(", ")
)
# A title that says it builds software is never hidden by the lists above.
BUILDER_TITLES = tuple(
    "software, backend, back-end, frontend, front-end, full stack, full-stack, fullstack, data scientist, "
    "machine learning, ml engineer, site reliability, platform engineer, data engineer, devops".split(", ")
)


def title_ok(title: str, include: list[str], exclude: list[str], presales: bool) -> bool:
    if has_any(title, exclude, hyphen_joins=True):
        return False
    if not has_any(title, BUILDER_TITLES, hyphen_joins=True) and _hidden(title, include, presales):
        return False
    return has_any(title, include or DEFAULT_TITLES, hyphen_joins=True)


def _hidden(title: str, include: list[str], presales: bool) -> bool:
    if not presales and has_any(title, PRESALES_TITLES, hyphen_joins=True):
        return True
    for phrases in (NON_DEV_TITLES, HARDWARE_TITLES):
        named = any(has_any(t, phrases, hyphen_joins=True) for t in include)
        if not named and has_any(title, phrases, hyphen_joins=True):
            return True
    return False
