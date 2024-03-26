from .schema import Schema, LexicalScope


class DynamicScope:

    def __init__(
        self,
        current_lexical_scope: LexicalScope,
        prev_dynamic_scope: "DynamicScope | None"
    ):
        self.lexical_scope = current_lexical_scope
        self.prev_dynamic_scope = prev_dynamic_scope
        self.evaluated_props = set[str]()
        self.evaluated_items = set[int]()


class Vocabulary:
    by_uri = dict[str, type["Vocabulary"]]()

    @staticmethod
    def on_schema_init(
        schema: Schema,
        schema_by_uri: dict[str, "Schema | dict | bool"],
        refs: list
    ):
        pass

    # @staticmethod
    # def on_schema_post_init(
    #     schema: Schema,
    #     schema_by_uri: dict[str, "Schema | dict | bool"]
    # ):
    #     pass

    @staticmethod
    def validate(
        schema: Schema,
        instance,
        dynamic_scope: DynamicScope
    ):
        pass
