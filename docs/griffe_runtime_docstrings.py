"""Merge Cython runtime docstrings into Griffe's statically loaded stubs."""

from inspect import cleandoc

import griffe

_CYTHON_MODULES = ("ngh2._core.", "ngh2.events.")


def _without_cython_signature(docstring: str, name: str) -> str:
    docstring = cleandoc(docstring)
    first, separator, body = docstring.partition("\n\n")
    callable_name = first.partition("(")[0].rsplit(".", 1)[-1]
    if separator and first.endswith(")") and callable_name == name:
        return body
    return docstring


class RuntimeDocstrings(griffe.Extension):
    """Copy compiled-object documentation without replacing stub signatures."""

    def on_object(
        self,
        *,
        obj: griffe.Object,
        loader: griffe.GriffeLoader,
        **kwargs: object,
    ) -> None:
        if (
            obj.docstring
            or obj.name.startswith("_")
            or not obj.path.startswith(_CYTHON_MODULES)
            or not (obj.is_class or obj.is_function or "property" in obj.labels)
        ):
            return

        runtime_docstring = getattr(griffe.dynamic_import(obj.path), "__doc__", None)
        if runtime_docstring:
            obj.docstring = griffe.Docstring(
                _without_cython_signature(runtime_docstring, obj.name),
                parent=obj,
                parser=loader.docstring_parser,
                parser_options=loader.docstring_options,
            )


if __name__ == "__main__":
    package = griffe.load(
        "ngh2",
        search_paths=["src"],
        extensions=griffe.Extensions(RuntimeDocstrings()),
        docstring_parser="google",
    )
    connection = package.members["Connection"].target
    send_request = connection.members["send_request"]
    data_received = package.members["DataReceived"].target

    assert "Queue request headers" in send_request.docstring.value
    assert "Sequence[Header]" in str(send_request.signature())
    assert data_received.docstring.value.startswith("One complete DATA frame")
