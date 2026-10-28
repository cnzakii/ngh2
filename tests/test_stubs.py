"""Keep the hand-written stubs aligned with the compiled runtime API."""

import ast
import inspect
import re
from collections.abc import Callable
from pathlib import Path

import pytest

import ngh2
from ngh2 import _core, events

PACKAGE = Path(ngh2.__file__).parent


def stub_classes(module_name: str) -> list[tuple[str, ast.ClassDef]]:
    tree = ast.parse((PACKAGE / f"{module_name}.pyi").read_text())
    return [(node.name, node) for node in tree.body if isinstance(node, ast.ClassDef)]


def stub_parameters(function: ast.FunctionDef) -> list[tuple[str, str, bool]]:
    arguments = function.args
    positional = arguments.posonlyargs + arguments.args
    defaults = [False] * (len(positional) - len(arguments.defaults))
    defaults += [True] * len(arguments.defaults)
    result = [
        (argument.arg, "positional", has_default)
        for argument, has_default in zip(positional, defaults, strict=True)
    ]
    result += [
        (argument.arg, "keyword", default is not None)
        for argument, default in zip(
            arguments.kwonlyargs, arguments.kw_defaults, strict=True
        )
    ]
    return [parameter for parameter in result if parameter[0] != "self"]


def runtime_parameters(
    function: Callable[..., object],
) -> list[tuple[str, str, bool]]:
    keyword_only = inspect.Parameter.KEYWORD_ONLY
    return [
        (
            parameter.name,
            "keyword" if parameter.kind is keyword_only else "positional",
            parameter.default is not inspect.Parameter.empty,
        )
        for parameter in inspect.signature(function).parameters.values()
        if parameter.name != "self"
    ]


def embedded_constructor_parameters(cls: type) -> list[tuple[str, str, bool]]:
    # Cython embeds "Name(type arg, type arg=default)" for slot constructors.
    first_line = (cls.__doc__ or "").splitlines()[0]
    inside = first_line[first_line.index("(") + 1 : first_line.rindex(")")]
    result = []
    kind = "positional"
    for item in filter(None, (part.strip() for part in inside.split(","))):
        if item == "*":
            kind = "keyword"
            continue
        name = re.findall(r"\w+", item.partition("=")[0])[-1]
        result.append((name, kind, "=" in item))
    return result


CLASSES = [
    (module, name, node)
    for module, module_name in ((_core, "_core"), (events, "events"))
    for name, node in stub_classes(module_name)
]


@pytest.mark.parametrize(
    ("module", "name", "node"), CLASSES, ids=[name for _, name, _ in CLASSES]
)
def test_stub_members_match_runtime(
    module: object, name: str, node: ast.ClassDef
) -> None:
    cls = getattr(module, name)
    stubbed = {
        item.name: item for item in node.body if isinstance(item, ast.FunctionDef)
    }
    public = {
        member
        for member in vars(cls)
        if not member.startswith("_") and member != "__match_args__"
    }
    assert public <= set(stubbed) | {"__match_args__"}, public - set(stubbed)

    for member, function in stubbed.items():
        is_property = any(
            isinstance(decorator, ast.Name) and decorator.id == "property"
            for decorator in function.decorator_list
        )
        runtime = inspect.getattr_static(cls, member)
        if is_property:
            assert inspect.isgetsetdescriptor(runtime) or isinstance(
                runtime, property
            ), member
        elif member == "__init__":
            assert stub_parameters(function) == embedded_constructor_parameters(cls)
        else:
            assert stub_parameters(function) == runtime_parameters(
                getattr(cls, member)
            ), member


def test_stub_functions_match_runtime() -> None:
    tree = ast.parse((PACKAGE / "_core.pyi").read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]

    assert functions
    for function in functions:
        runtime = getattr(_core, function.name)
        assert stub_parameters(function) == runtime_parameters(runtime)
