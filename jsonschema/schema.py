from typing import TYPE_CHECKING
from copy import deepcopy

if TYPE_CHECKING:
    from .vocabulary import DynamicScope


class LexicalScope:

    def __init__(
        self,
        root_schema: "Schema"
    ):
        self.root_schema = root_schema
        self.anchors = dict[str, "Schema"]()
        self.dynamic_anchors = dict[str, "Schema"]()


class Schema:
    scope: LexicalScope

    def __init__(
        self,
        data: dict | bool,
        meta_schema: "Schema | None" = None,
        should_not_have_meta=False,
        parent: "Schema | None" = None,
        uri: str | None = None,
        schema_by_uri: dict[str, "Schema | dict | bool"] | None = None,
        refs: list | None = None
    ):
        if schema_by_uri is None:
            schema_by_uri = dict()

        if isinstance(data, bool):
            if data:
                data = {}
            else:
                data = {"not": {}}

        from .vocabulary import Vocabulary

        self.parent = parent
        self.uri = uri

        if meta_schema is None:
            if should_not_have_meta:
                pass
            elif "$schema" in data:
                _meta_uri = data["$schema"]
                _meta_schema = schema_by_uri[_meta_uri]
                if not isinstance(_meta_schema, Schema):
                    _meta_schema = Schema(
                        _meta_schema,
                        uri=_meta_uri,
                        schema_by_uri=schema_by_uri
                    )
                meta_schema = _meta_schema
            elif parent is not None:
                meta_schema = parent.meta_schema
            else:
                from .draft_2020_12 import raw
                meta_schema = raw.META

        self.meta_schema = meta_schema

        self.fields = deepcopy(data)

        if self.meta_schema is not None:
            if refs is None:
                post = True
                refs = list()
            else:
                post = False

            for v in self.meta_schema.fields["$vocabulary"]:
                assert issubclass(v, Vocabulary)
                v.on_schema_init(
                    schema=self,
                    schema_by_uri=schema_by_uri,
                    refs=refs
                )

            if post:
                for r in refs:
                    r()

    def validate(
        self,
        instance,
        prev_scope: "DynamicScope | None" = None
    ):
        from .vocabulary import Vocabulary, DynamicScope

        scope = DynamicScope(self.scope, prev_dynamic_scope=prev_scope)

        assert self.meta_schema is not None

        for v in self.meta_schema.fields["$vocabulary"]:
            assert issubclass(v, Vocabulary)
            result = v.validate(
                self,
                instance,
                scope
            )
            if result is False:
                return False

        if prev_scope is not None:
            prev_scope.evaluated_props.update(scope.evaluated_props)
            prev_scope.evaluated_items.update(scope.evaluated_items)

        return True
