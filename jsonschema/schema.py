from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .vocabulary import Vocabulary, DynamicScope


class LexicalScope:

    def __init__(
        self,
        schema: "Schema",
        schema_by_uri: dict[str, "Schema"]
    ):
        self.schema = schema
        self.anchors = dict[str, "Schema"]()
        self.dynamic_anchors = dict[str, "Schema"]()
        self.schema_by_uri = schema_by_uri


class Schema:
    scope: LexicalScope
    vocabularies: list["Vocabulary"]

    def __init__(
        self,
        schema: dict | bool,
        vocabularies: list["Vocabulary"] | None = None,
        parent: "Schema | None" = None,
        uri: str | None = None
    ):
        self.parent = parent
        self.uri = uri
        self.fields = dict[str, Any]()

        if vocabularies is None and parent is not None:
            vocabularies = parent.vocabularies

        assert vocabularies is not None

        self.vocabularies = vocabularies

        if isinstance(schema, bool):
            if schema:
                schema = {}
            else:
                schema = {"not": {}}

        for v in self.vocabularies:
            v.on_schema_init(schema=self, raw_schema=schema)

        for k, v in schema.items():
            if k not in self.fields:
                self.fields[k] = v

    def validate(
        self,
        instance,
        schema_by_uri: dict[str, "Schema"],
        prev_scope: "DynamicScope | None" = None
    ):
        from .vocabulary import DynamicScope

        scope = DynamicScope(self.scope, prev_dynamic_scope=prev_scope)

        for v in self.vocabularies:
            result = v.validate(
                self,
                instance,
                schema_by_uri,
                scope
            )
            if result is False:
                return False

        if prev_scope is not None:
            prev_scope.evaluated_props.update(scope.evaluated_props)
            prev_scope.evaluated_items.update(scope.evaluated_items)

        return True

