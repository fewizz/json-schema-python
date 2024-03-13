from typing import Any
import numbers
import math
import re
import copy


class JSONSchema:

    def __init__(
        self,
        schema: dict | bool,
        schema_by_uri: dict[str, dict] | None = None,
        parent: "JSONSchema | None" = None,
        subs: "list[JSONSchema] | None" = None
    ):
        self.parent = parent
        if subs is None:
            subs = list[JSONSchema]()
            check_subs = True
        else:
            check_subs = False

        if isinstance(schema, bool):
            if schema:
                schema = {}
            else:
                schema = {"not": {}}

        if parent is None or "$id" in schema:
            self.root = self
            self.anchors = dict[str, JSONSchema]()
            self.dynamic_anchors = dict[str, JSONSchema]()
        else:
            self.root = parent.root
            self.anchors = parent.anchors
            self.dynamic_anchors = parent.dynamic_anchors

        if parent is None:
            if schema_by_uri is not None:
                self.schema_by_uri = copy.deepcopy(schema_by_uri)
            else:
                self.schema_by_uri = dict[str, dict]()
        else:
            self.schema_by_uri = parent.schema_by_uri

        subs.append(self)

        self.uri = None

        if "$id" in schema:
            uri = schema["$id"]
            assert isinstance(uri, str)

            # TODO this is wrong
            schemas = ("http://", "https://")
            if not uri.startswith(schemas):
                p = parent
                while True:
                    assert p is not None
                    root_uri = p.root.uri
                    if root_uri is not None and root_uri.startswith(schemas):
                        break
                    p = p.parent

                uri_parts = root_uri.split("/")
                uri = "/".join(uri_parts[0:-1]) + "/" + uri

            self.schema_by_uri[uri] = schema
            self.uri = uri

        if "$anchor" in schema:
            anchor = schema["$anchor"]
            self.anchors[anchor] = self

        if "$dynamicAnchor" in schema:
            self.dynamic_anchors[schema["$dynamicAnchor"]] = self

        self.fields = dict[str, Any]()

        for k, v in schema.items():
            if k in (
                "if", "then", "else", "not", "contains",
                "additionalProperties", "items", "unevaluatedItems",
                "unevaluatedProperties", "propertyNames"
            ):
                self.fields[k] = JSONSchema(
                    schema=v,
                    parent=self,
                    subs=subs
                )
            elif k in (
                "allOf", "anyOf", "oneOf", "prefixItems"
            ):
                self.fields[k] = [
                    JSONSchema(
                        schema=sub_schema,
                        parent=self,
                        subs=subs
                    )
                    for sub_schema in v
                ]
            elif k in (
                "properties", "patternProperties", "dependentSchemas",
                "$defs"
            ):
                self.fields[k] = {
                    name: JSONSchema(
                        schema=sub_schema,
                        parent=self,
                        subs=subs
                    )
                    for name, sub_schema in v.items()
                }
            else:
                self.fields[k] = v

        if check_subs:
            for sub in subs:
                if "$ref" in sub.fields:
                    ref = self._reference(sub.fields["$ref"], dynamic=False)
                    assert isinstance(ref, JSONSchema)
                    sub.fields["$ref"] = ref

    def validate(self, instance, evaluated_properties: set[str] | None = None):
        if evaluated_properties is None:
            evaluated_properties = set[str]()

        if "$ref" in self.fields:
            sub = self.fields["$ref"]
            assert isinstance(sub, JSONSchema)
            if not sub.validate(
                instance=instance,
                evaluated_properties=evaluated_properties
            ):
                return False

        if "$dynamicRef" in self.fields:
            uri = self.fields["$dynamicRef"]
            ref = self._reference(uri, dynamic=True)
            assert isinstance(ref, JSONSchema)
            if not ref.validate(
                instance=instance,
                evaluated_properties=evaluated_properties
            ):
                return False

        if "type" in self.fields:
            _type = self.fields["type"]
            if isinstance(_type, list):
                if not any(self._check_type(t, instance) for t in _type):
                    return False
            else:
                if not self._check_type(_type, instance):
                    return False

        if "not" in self.fields:
            sub = self.fields["not"]
            assert isinstance(sub, JSONSchema)
            if sub.validate(instance):
                return False

        if "const" in self.fields:
            if not JSONSchema._compare(instance, self.fields["const"]):
                return False

        if "oneOf" in self.fields:
            count = 0
            for sub in self.fields["oneOf"]:
                if sub.validate(
                    instance=instance,
                    evaluated_properties=evaluated_properties
                ):
                    count += 1
            if count != 1:
                return False

        if "allOf" in self.fields:
            for sub in self.fields["allOf"]:
                if not sub.validate(
                    instance=instance,
                    evaluated_properties=evaluated_properties
                ):
                    return False

        if "anyOf" in self.fields:
            count = 0
            for sub in self.fields["anyOf"]:
                if sub.validate(
                    instance=instance,
                    evaluated_properties=evaluated_properties
                ):
                    count += 1
            if count == 0:
                return False

        if "if" in self.fields:
            sub = self.fields["if"]
            assert isinstance(sub, JSONSchema)
            result = sub.validate(
                instance=instance,
                evaluated_properties=evaluated_properties
            )
            if result and "then" in self.fields:
                sub = self.fields["then"]
                assert isinstance(sub, JSONSchema)
                if not sub.validate(
                    instance=instance,
                    evaluated_properties=evaluated_properties
                ):
                    return False
                else:
                    pass
            if not result and "else" in self.fields:
                sub = self.fields["else"]
                assert isinstance(sub, JSONSchema)
                if not sub.validate(
                    instance=instance,
                    evaluated_properties=evaluated_properties
                ):
                    return False
                else:
                    pass

        if isinstance(instance, numbers.Real):
            if "minimum" in self.fields and instance < self.fields["minimum"]:
                return False

            if "maximum" in self.fields and instance > self.fields["maximum"]:
                return False

            if (
                "exclusiveMaximum" in self.fields
                and instance >= self.fields["exclusiveMaximum"]
            ):
                return False

            if "multipleOf" in self.fields:
                multiple = self.fields["multipleOf"]
                mod = instance % multiple
                if not (
                    mod == 0 or (multiple - mod) < 0.00001
                ):
                    return False

        if isinstance(instance, list):
            if "prefixItems" in self.fields:
                for index, sub in enumerate(self.fields["prefixItems"]):
                    assert isinstance(sub, JSONSchema)
                    if index >= len(instance):
                        break
                    if not sub.validate(instance[index]):
                        return False

            if "items" in self.fields:
                sub = self.fields["items"]
                assert isinstance(sub, JSONSchema)
                initial_index = 0
                if "prefixItems" in self.fields:
                    initial_index = len(self.fields["prefixItems"])

                if initial_index < len(instance):
                    for item in instance[initial_index:]:
                        if not sub.validate(item):
                            return False

            if (
                "minItems" in self.fields
                and len(instance) < self.fields["minItems"]
            ):
                return False

            if (
                "maxItems" in self.fields
                and len(instance) > self.fields["maxItems"]
            ):
                return False

        if isinstance(instance, str):
            if (
                "minLength" in self.fields
                and len(instance) < self.fields["minLength"]
            ):
                return False

            if (
                "maxLength" in self.fields
                and len(instance) > self.fields["maxLength"]
            ):
                return False

            if (
                "pattern" in self.fields
                and not re.search(
                    pattern=self.fields["pattern"],
                    string=instance
                )
            ):
                return False

        if isinstance(instance, dict):
            if (
                "minProperties" in self.fields
                and len(instance) < self.fields["minProperties"]
            ):
                return False

            if (
                "maxProperties" in self.fields
                and len(instance) > self.fields["maxProperties"]
            ):
                return False

            if "required" in self.fields:
                for key in self.fields["required"]:
                    if key not in instance:
                        return False

            if "dependentSchemas" in self.fields:
                for prop_name, sub in self.fields["dependentSchemas"].items():
                    assert isinstance(sub, JSONSchema)
                    valid = True
                    if prop_name in instance:
                        valid &= sub.validate(
                            instance=instance,
                            evaluated_properties=evaluated_properties
                        )
                    if not valid:
                        return False

            locally_evaluated_properties = set[str]()

            if "patternProperties" in self.fields:
                for key in instance:
                    for pattern, sub in self.fields["patternProperties"].items():
                        assert isinstance(sub, JSONSchema)
                        if re.search(
                            pattern=pattern,
                            string=key
                        ):
                            if not sub.validate(
                                instance=instance[key],
                                evaluated_properties=evaluated_properties
                            ):
                                return False
                            locally_evaluated_properties.add(key)

            if "properties" in self.fields:
                for key, sub in self.fields["properties"].items():
                    assert isinstance(sub, JSONSchema)
                    if key in instance:
                        if not sub.validate(
                            instance=instance[key],
                            evaluated_properties=evaluated_properties
                        ):
                            return False
                        locally_evaluated_properties.add(key)

            if "additionalProperties" in self.fields:
                sub = self.fields["additionalProperties"]
                assert isinstance(sub, JSONSchema)
                for key in instance:
                    if key not in locally_evaluated_properties:
                        if not sub.validate(
                            instance=instance[key],
                            evaluated_properties=evaluated_properties
                        ):
                            return False
                        locally_evaluated_properties.add(key)

            evaluated_properties.update(locally_evaluated_properties)

            if "unevaluatedProperties" in self.fields:
                sub = self.fields["unevaluatedProperties"]
                assert isinstance(sub, JSONSchema)

                for key in instance:
                    if key not in evaluated_properties:
                        if not sub.validate(
                            instance=instance[key],
                            evaluated_properties=evaluated_properties
                        ):
                            return False
                        evaluated_properties.add(key)

        return True

    def _check_type(self, type: str, instance):
        match type:
            case "null":
                return instance is None
            case "string":
                return isinstance(instance, str)
            case "object":
                return isinstance(instance, dict)
            case "array":
                return isinstance(instance, list)
            case "boolean":
                return isinstance(instance, bool)
            case "integer":
                match instance:
                    case bool():
                        return False
                    case int():
                        return True
                    case float():
                        return math.modf(instance)[0] == 0.0
                    case _:
                        return False
            case "number":
                match instance:
                    case bool():
                        return False
                    case int():
                        return True
                    case float():
                        return True
                    case _:
                        return False
        return False

    @staticmethod
    def _compare(a, b):
        if (
            type(a) is bool and type(b) is not bool or
            type(b) is bool and type(a) is not bool
        ):
            return False

        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                return False
            for aa, bb in zip(a, b):
                if not JSONSchema._compare(aa, bb):
                    return False
            return True
        elif isinstance(a, dict) and isinstance(b, dict):
            if len(a) != len(b):
                return False
            for key in a:
                if key not in b or not JSONSchema._compare(a[key], b[key]):
                    return False
            return True
        else:
            return a == b

    def _reference(self, uri: str, dynamic: bool) -> "JSONSchema | None":
        try:
            fragment_start_index = uri.index("#")
            fragment = uri[fragment_start_index:]
            uri = uri[0:fragment_start_index]
        except ValueError:
            fragment = None

        schema = None

        if (
            uri.startswith("http://")
            or uri.startswith("https://")
        ):
            schema = JSONSchema(
                schema=self.schema_by_uri[uri],
                parent=self
            )
        elif len(uri) > 0:
            base = self.uri
            assert isinstance(base, str)

            if uri.startswith("/"):
                pass
            else:
                base_parts = base.split("/")
                base = "/".join(base_parts[0:-1]) + "/"

            schema = JSONSchema(
                schema=self.schema_by_uri[base + uri],
                parent=self
            )
        else:
            schema = self.root

        if fragment is not None:
            schema = schema._fragment_reference(fragment, dynamic=dynamic)

        return schema

    def _fragment_reference(
        self,
        fragment: str,
        dynamic: bool
    ) -> "JSONSchema | None":
        assert fragment.startswith("#")
        fragment = fragment[1:]

        if not dynamic:
            if fragment in self.anchors:
                return self.anchors[fragment]
            if fragment in self.dynamic_anchors:
                return self.dynamic_anchors[fragment]
        else:
            found = None

            root = self.root
            while root is not None:
                if fragment not in root.dynamic_anchors:
                    break

                found = root.dynamic_anchors[fragment]

                if root.parent is not None:
                    root = root.parent.root
                else:
                    root = None

            if found is not None:
                return found

            if fragment in self.anchors:
                return self.anchors[fragment]

        def reference0(
            path: list[str],
            schema: JSONSchema | list | dict,
        ):
            if len(path) == 0:
                assert isinstance(schema, JSONSchema)
                return schema

            p = path[0]
            p_unpacked = list()

            i = 0
            while i < len(p):
                ch = p[i]

                if ch == "~":
                    i += 1
                    if p[i] == "0":
                        ch = "~"
                    elif p[i] == "1":
                        ch = "/"
                elif ch == "%":
                    ch = chr(int(p[i+1:i+3], 16))
                    i += 2

                p_unpacked.append(ch)
                i += 1

            p = "".join(p_unpacked)

            if p.isdigit():
                assert isinstance(schema, list)
                index = int(p)
                if index < len(schema):
                    return reference0(
                        path[1:],
                        schema=schema[index]
                    )
            else:
                if isinstance(schema, dict):
                    if p in schema:
                        return reference0(
                            path[1:],
                            schema=schema[p]
                        )
                elif isinstance(schema, JSONSchema):
                    if p in schema.fields:
                        return reference0(
                            path[1:],
                            schema=schema.fields[p]
                        )
            return None

        return reference0(fragment.split("/")[1:], self)


class Validator:

    
    def validate(
        self, instance,
        schema: dict | bool | None = None,
        usedProperties: set[str] | None = None
    ):
        if schema is None:
            schema = self.schema
        if usedProperties is None:
            usedProperties = set()

        if schema is True:
            return True
        if schema is False:
            return False

        if "contains" in schema and isinstance(instance, list):
            sch = schema["contains"]
            for i in instance:
                if self.validate(
                    instance=i,
                    schema=sch
                ):
                    break
            else:
                return False

        if "enum" in schema:
            enum: list = schema["enum"]
            if instance not in enum:
                return False
            val = enum[enum.index(instance)]

            if not compare(instance, val):
                return False

        return True
