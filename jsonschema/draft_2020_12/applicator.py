import re
import sys
from ..vocabulary import Vocabulary, Schema, DynamicScope


class Applicator(Vocabulary):

    @staticmethod
    def on_schema_init(schema: Schema, raw_schema: dict):
        for k, v in raw_schema.items():
            if k in (
                "items", "contains", "additionalProperties",
                "propertyNames", "if", "then", "else", "not"
            ):
                schema.fields[k] = Schema(
                    schema=v,
                    parent=schema
                )
            elif k in (
                "prefixItems", "allOf", "anyOf", "oneOf"
            ):
                schema.fields[k] = [
                    Schema(
                        schema=sub_schema,
                        parent=schema
                    )
                    for sub_schema in v
                ]
            elif k in (
                "properties", "patternProperties", "dependentSchemas"
            ):
                schema.fields[k] = {
                    name: Schema(
                        schema=sub_schema,
                        parent=schema
                    )
                    for name, sub_schema in v.items()
                }

    @staticmethod
    def validate(
        s: Schema,
        instance,
        schema_by_uri: dict[str, "Schema"],
        scope: DynamicScope
    ):
        if "not" in s.fields:
            sub = s.fields["not"]
            assert isinstance(sub, Schema)
            if sub.validate(
                instance,
                schema_by_uri=schema_by_uri,
                prev_scope=scope
            ):
                return False

        if "oneOf" in s.fields:
            count = 0
            for sub in s.fields["oneOf"]:
                assert isinstance(sub, Schema)
                # locally_evaluated_properties_0 = set[str]()
                if sub.validate(
                    instance=instance,
                    schema_by_uri=schema_by_uri,
                    prev_scope=scope
                ):
                    count += 1
            if count != 1:
                return False

        if "anyOf" in s.fields:
            count = 0
            for sub in s.fields["anyOf"]:
                assert isinstance(sub, Schema)
                # locally_evaluated_properties_0 = set[str]()
                if sub.validate(
                    instance=instance,
                    schema_by_uri=schema_by_uri,
                    prev_scope=scope
                ):
                    count += 1
            if count == 0:
                return False

        if "allOf" in s.fields:
            count = 0
            subs = s.fields["allOf"]
            for sub in subs:
                assert isinstance(sub, Schema)
                # locally_evaluated_properties = set[str]()
                if sub.validate(
                    instance=instance,
                    schema_by_uri=schema_by_uri,
                    prev_scope=scope
                ):
                    count += 1
                # evaluated_properties.update(locally_evaluated_properties)
            if count != len(subs):
                return False

        if "if" in s.fields:
            sub = s.fields["if"]
            assert isinstance(sub, Schema)
            result = sub.validate(
                instance=instance,
                schema_by_uri=schema_by_uri,
                prev_scope=scope
            )
            if result and "then" in s.fields:
                sub = s.fields["then"]
                assert isinstance(sub, Schema)
                if not sub.validate(
                    instance=instance,
                    schema_by_uri=schema_by_uri,
                    prev_scope=scope
                ):
                    return False
                else:
                    pass
            if not result and "else" in s.fields:
                sub = s.fields["else"]
                assert isinstance(sub, Schema)
                if not sub.validate(
                    instance=instance,
                    schema_by_uri=schema_by_uri,
                    prev_scope=scope
                ):
                    return False
                else:
                    pass

        if isinstance(instance, list):
            locally_evaluated_items = set[int]()

            if "prefixItems" in s.fields:
                for index, sub in enumerate(s.fields["prefixItems"]):
                    assert isinstance(sub, Schema)
                    if index >= len(instance):
                        break
                    item = instance[index]
                    if not sub.validate(
                        item,
                        schema_by_uri=schema_by_uri,
                        prev_scope=scope
                    ):
                        return False
                    locally_evaluated_items.add(index)

            if "items" in s.fields:
                sub = s.fields["items"]
                assert isinstance(sub, Schema)
                initial_index = 0
                if "prefixItems" in s.fields:
                    initial_index = len(s.fields["prefixItems"])

                if initial_index < len(instance):
                    for index, item in enumerate(
                        instance[initial_index:],
                        start=initial_index
                    ):
                        if not sub.validate(
                            item,
                            schema_by_uri=schema_by_uri,
                            prev_scope=scope
                        ):
                            return False
                        # elif item not in evaluated_items:
                        #    locally_evaluated_items.append(item)
                        locally_evaluated_items.add(index)

            if "contains" in s.fields:
                sub = s.fields["contains"]
                assert isinstance(sub, Schema)

                min_contains: int = s.fields.get("minContains", 1)
                max_contains: int = s.fields.get(
                    "maxContains", sys.maxsize
                )

                count = 0
                for index, i in enumerate(instance):
                    if sub.validate(
                        instance=i,
                        schema_by_uri=schema_by_uri,
                        prev_scope=scope
                    ):
                        count += 1
                        locally_evaluated_items.add(index)

                if count < min_contains or count > max_contains:
                    return False

            scope.evaluated_items.update(locally_evaluated_items)

        if isinstance(instance, dict):
            if "propertyNames" in s.fields:
                sub = s.fields["propertyNames"]
                assert isinstance(sub, Schema)

                for prop_name in instance.keys():
                    if not sub.validate(
                        instance=prop_name,
                        schema_by_uri=schema_by_uri,
                        prev_scope=scope
                    ):
                        return False

            if "dependentSchemas" in s.fields:
                items = s.fields["dependentSchemas"].items()
                for prop_name, sub in items:
                    assert isinstance(sub, Schema)
                    valid = True
                    if prop_name in instance:
                        valid &= sub.validate(
                            instance=instance,
                            schema_by_uri=schema_by_uri,
                            prev_scope=scope
                        )
                    if not valid:
                        return False

            locally_evaluated_props = set[str]()

            if "patternProperties" in s.fields:
                for key in instance:
                    props: dict[str, Schema] \
                        = s.fields["patternProperties"]
                    for pattern, sub in props.items():
                        assert isinstance(sub, Schema)
                        if re.search(
                            pattern=pattern,
                            string=key
                        ):
                            if not sub.validate(
                                instance=instance[key],
                                schema_by_uri=schema_by_uri,
                                prev_scope=scope
                            ):
                                return False
                            locally_evaluated_props.add(key)

            if "properties" in s.fields:
                for key, sub in s.fields["properties"].items():
                    assert isinstance(sub, Schema)
                    if key in instance:
                        if not sub.validate(
                            instance=instance[key],
                            schema_by_uri=schema_by_uri,
                            prev_scope=scope
                        ):
                            return False
                        locally_evaluated_props.add(key)

            if "additionalProperties" in s.fields:
                sub = s.fields["additionalProperties"]
                assert isinstance(sub, Schema)
                for key in instance:
                    if key not in locally_evaluated_props:
                        if not sub.validate(
                            instance=instance[key],
                            schema_by_uri=schema_by_uri,
                            prev_scope=scope
                        ):
                            return False
                        locally_evaluated_props.add(key)

            scope.evaluated_props.update(locally_evaluated_props)
