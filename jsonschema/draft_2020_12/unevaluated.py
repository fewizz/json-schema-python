from ..vocabulary import Vocabulary, Schema, DynamicScope


class Unevaluated(Vocabulary):

    @staticmethod
    def on_schema_init(schema: Schema):
        if "unevaluatedItems" in schema.fields:
            schema.fields["unevaluatedItems"] = Schema(
                data=schema.fields["unevaluatedItems"],
                parent=schema
            )

        if "unevaluatedProperties" in schema.fields:
            schema.fields["unevaluatedProperties"] = Schema(
                data=schema.fields["unevaluatedProperties"],
                parent=schema
            )

    @staticmethod
    def validate(
        s: Schema,
        instance,
        schema_by_uri: dict[str, "Schema"],
        scope: DynamicScope
    ):
        if (
            isinstance(instance, list)
            and "unevaluatedItems" in s.fields
        ):
            sub = s.fields["unevaluatedItems"]
            assert isinstance(sub, Schema)

            for index, item in enumerate(instance):
                if index not in scope.evaluated_items:
                    if not sub.validate(
                        instance=item,
                        schema_by_uri=schema_by_uri,
                        prev_scope=scope,
                    ):
                        return False
                    scope.evaluated_items.add(index)

        if (
            isinstance(instance, dict)
            and "unevaluatedProperties" in s.fields
        ):
            sub = s.fields["unevaluatedProperties"]
            assert isinstance(sub, Schema)

            for key in instance:
                if key not in scope.evaluated_props:
                    if not sub.validate(
                        instance=instance[key],
                        schema_by_uri=schema_by_uri,
                        prev_scope=scope
                    ):
                        return False
                    scope.evaluated_props.add(key)


Vocabulary.by_uri[
    "https://json-schema.org/draft/2020-12/vocab/unevaluated"
] = Unevaluated
