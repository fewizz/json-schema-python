from typing import TYPE_CHECKING
from copy import deepcopy

if TYPE_CHECKING:
    from .vocabulary import DynamicScope


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

    def __init__(
        self,
        data: dict | bool,
        schema: "Schema | None" = None,
        parent: "Schema | None" = None,
        uri: str | None = None
    ):
        from .vocabulary import Vocabulary

        self.parent = parent
        self.uri = uri

        if schema is None and parent is not None:
            schema = parent.schema

        self.schema = schema

        if isinstance(data, bool):
            if data:
                data = {}
            else:
                data = {"not": {}}

        self.fields = deepcopy(data)

        if self.schema is not None:
            for v in self.schema.fields["$vocabulary"]:
                assert issubclass(v, Vocabulary)
                v.on_schema_init(schema=self)

            for k, v in data.items():
                if k not in self.fields:
                    self.fields[k] = v

    def validate(
        self,
        instance,
        schema_by_uri: dict[str, "Schema"],
        prev_scope: "DynamicScope | None" = None
    ):
        from .vocabulary import Vocabulary, DynamicScope

        scope = DynamicScope(self.scope, prev_dynamic_scope=prev_scope)

        assert self.schema is not None

        for v in self.schema.fields["$vocabulary"]:
            assert issubclass(v, Vocabulary)
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
