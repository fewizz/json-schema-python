from ..vocabulary import Vocabulary, Schema, DynamicScope


class Unevaluated(Vocabulary):

    @staticmethod
    def on_schema_init(schema: Schema, raw_schema: dict):
        if "unevaluatedItems" in raw_schema:
            schema.fields["unevaluatedItems"] = Schema(
                schema=raw_schema["unevaluatedItems"],
                parent=schema
            )

        if "unevaluatedProperties" in raw_schema:
            schema.fields["unevaluatedProperties"] = Schema(
                schema=raw_schema["unevaluatedProperties"],
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
