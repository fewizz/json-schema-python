from .schema import Schema, LexicalScope


class DynamicScope:

    def __init__(
        self,
        current_scope: LexicalScope,
        prev_dynamic_scope: "DynamicScope | None"
    ):
        self.scope = current_scope
        self.prev_dynamic_handle = prev_dynamic_scope
        self.evaluated_props = set[str]()
        self.evaluated_items = set[int]()


class Vocabulary:
    by_uri = dict[str, type["Vocabulary"]]()

    @staticmethod
    def on_schema_init(schema: Schema):
        pass

    @staticmethod
    def validate(
        schema: Schema,
        instance,
        schema_by_uri: dict[str, "Schema"],
        dynamic_scope: DynamicScope
    ):
        pass
