from typing import Any
import numbers
import math
import re
import copy


# class JSONSchema:

#     def __init__(self, schema: dict | bool, content_by_uid):
#         assert 
#         self.content_by_uri = copy.deepcopy(content_by_uid)

#         self.keywords = dict[str, Any]()

#         for k, v in schema.items():


class Validator:

    def __init__(self, schema: dict | bool, content_by_uid):
        self.schema = schema
        self.content_by_uri = copy.deepcopy(content_by_uid)
        self.dynamic_anchors = dict[str, dict | bool]()

        if isinstance(self.schema, dict):
            if "$id" in self.schema:
                self.content_by_uri[self.schema["$id"]] = self.schema

            for def_sch in self.schema.get("$defs", dict()).values():
                if isinstance(def_sch, dict) and "$id" in def_sch:
                    self.content_by_uri[def_sch["$id"]] = def_sch

    def check_type(self, type: str, instance):
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

    def fragment_reference(self, fragment: str) -> dict | bool:
        def reference0(path: list[str], schema):
            if len(path) == 0:
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
                index = int(p)
                if index < len(schema):
                    return reference0(path[1:], schema=schema[index])
            else:
                if p in schema:
                    return reference0(path[1:], schema=schema[p])
            return False

        return reference0(fragment.split("/")[1:], self.schema)

    def reference(
        self,
        uri: str,
        instance,
        usedProperties: set[str]
    ):
        try:
            fragment_start_index = uri.index("#")
            fragment = uri[fragment_start_index:]
            uri = uri[0:fragment_start_index]
        except ValueError:
            fragment = None

        resulting_validator = None

        if (
            uri.startswith("http://")
            or uri.startswith("https://")
        ):
            resulting_validator = Validator(
                schema=self.content_by_uri[uri],
                content_by_uid=self.content_by_uri
            )
        elif len(uri) > 0:
            assert isinstance(self.schema, dict)
            base = self.schema["$id"]
            assert isinstance(base, str)

            if uri.startswith("/"):
                pass
            else:
                base_parts = base.split("/")
                base = "/".join(base_parts[0:-1]) + "/"

            resulting_validator = Validator(
                schema=self.content_by_uri[base + uri],
                content_by_uid=self.content_by_uri
            )
        else:
            resulting_validator = self

        if fragment is not None:
            schema = resulting_validator.fragment_reference(fragment)
        else:
            schema = None

        return resulting_validator.validate(
            instance=instance,
            schema=schema,
            usedProperties=usedProperties
        )

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

        if isinstance(schema, dict) and "$ref" in schema:
            if not self.reference(
                uri=schema["$ref"],
                instance=instance,
                usedProperties=usedProperties
            ):
                return False

        if "prefixItems" in schema and isinstance(instance, list):
            for index, sch in enumerate(schema["prefixItems"]):
                if index >= len(instance):
                    break
                if not self.validate(
                    instance=instance[index],
                    schema=sch
                ):
                    return False

        if "type" in schema:
            _type = schema["type"]
            if isinstance(_type, list):
                if not any(self.check_type(t, instance) for t in _type):
                    return False
            else:
                if not self.check_type(_type, instance):
                    return False

        if "minimum" in schema:
            if (
                isinstance(instance, numbers.Real)
                and instance < schema["minimum"]
            ):
                return False

        if "maximum" in schema:
            if (
                isinstance(instance, numbers.Real)
                and instance > schema["maximum"]
            ):
                return False

        if "exclusiveMaximum" in schema:
            if (
                isinstance(instance, numbers.Real)
                and instance >= schema["exclusiveMaximum"]
            ):
                return False

        if "minLength" in schema:
            if (
                isinstance(instance, str)
                and len(instance) < schema["minLength"]
            ):
                return False

        if "maxLength" in schema:
            if (
                isinstance(instance, str)
                and len(instance) > schema["maxLength"]
            ):
                return False

        if "minProperties" in schema:
            if (
                isinstance(instance, dict)
                and len(instance) < schema["minProperties"]
            ):
                return False

        if "maxProperties" in schema:
            if (
                isinstance(instance, dict)
                and len(instance) > schema["maxProperties"]
            ):
                return False

        if "multipleOf" in schema and isinstance(instance, numbers.Real):
            multiple = schema["multipleOf"]
            mod = instance % multiple
            if not (
                mod == 0 or (multiple - mod) < 0.00001
            ):
                return False

        if "items" in schema and isinstance(instance, list):
            sch = schema["items"]
            for i in instance:
                if not self.validate(
                    instance=i,
                    schema=sch
                ):
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

        if isinstance(instance, dict):
            locallyUsedProperties = set[str]()
            if "patternProperties" in schema:
                for pattern, sch in schema["patternProperties"].items():
                    for key in instance:
                        if re.search(
                            pattern=pattern,
                            string=key
                        ):
                            if not self.validate(
                                instance=instance[key],
                                schema=sch
                            ):
                                return False
                            locallyUsedProperties.add(key)

            if "properties" in schema:
                for key, sch in schema["properties"].items():
                    if key in instance:
                        if not self.validate(
                            instance=instance[key],
                            schema=sch
                        ):
                            return False
                        locallyUsedProperties.add(key)

            if "additionalProperties" in schema:
                for key in instance:
                    if key not in locallyUsedProperties:
                        if not self.validate(
                            instance=instance[key],
                            schema=schema["additionalProperties"]
                        ):
                            return False
                        locallyUsedProperties.add(key)

            if "required" in schema:
                for key in schema["required"]:
                    if key not in instance:
                        return False

            usedProperties.update(locallyUsedProperties)

        def compare(a, b):
            if (
                type(a) is bool and type(b) is not bool or
                type(b) is bool and type(a) is not bool
            ):
                return False

            if isinstance(a, list) and isinstance(b, list):
                if len(a) != len(b):
                    return False
                for aa, bb in zip(a, b):
                    if not compare(aa, bb):
                        return False
                return True
            elif isinstance(a, dict) and isinstance(b, dict):
                if len(a) != len(b):
                    return False
                for key in a:
                    if key not in b or not compare(a[key], b[key]):
                        return False
                return True
            else:
                return a == b

        if "enum" in schema:
            enum: list = schema["enum"]
            if instance not in enum:
                return False
            val = enum[enum.index(instance)]

            if not compare(instance, val):
                return False

        if "const" in schema:
            if not compare(instance, schema["const"]):
                return False

        if "minItems" in schema:
            if (
                isinstance(instance, list)
                and len(instance) < schema["minItems"]
            ):
                return False

        if "maxItems" in schema:
            if (
                isinstance(instance, list)
                and len(instance) > schema["maxItems"]
            ):
                return False

        if "oneOf" in schema:
            count = 0
            for sch in schema["oneOf"]:
                if self.validate(
                    instance=instance,
                    schema=sch,
                    usedProperties=usedProperties
                ):
                    count += 1
            if count != 1:
                return False

        if "allOf" in schema:
            for sch in schema["allOf"]:
                if not self.validate(
                    instance=instance,
                    schema=sch,
                    usedProperties=usedProperties
                ):
                    return False

        if "anyOf" in schema:
            count = 0
            for sch in schema["anyOf"]:
                if self.validate(
                    instance=instance,
                    schema=sch,
                    usedProperties=usedProperties
                ):
                    count += 1
            if count == 0:
                return False

        if "dependentSchemas" in schema and isinstance(instance, dict):
            for prop_name, sch in schema["dependentSchemas"].items():
                valid = True
                if prop_name in instance:
                    valid &= self.validate(
                        instance=instance,
                        schema=sch,
                        usedProperties=usedProperties
                    )
                if not valid:
                    return False

        if "if" in schema:
            result = self.validate(
                instance=instance,
                schema=schema["if"],
                usedProperties=usedProperties
            )
            if result and "then" in schema:
                if not self.validate(
                    instance=instance,
                    schema=schema["then"],
                    usedProperties=usedProperties
                ):
                    return False
                else:
                    pass
            if not result and "else" in schema:
                if not self.validate(
                    instance=instance,
                    schema=schema["else"],
                    usedProperties=usedProperties
                ):
                    return False
                else:
                    pass

        if isinstance(instance, dict) and "unevaluatedProperties" in schema:
            for key in instance:
                if key not in usedProperties:
                    if not self.validate(
                        instance=instance[key],
                        schema=schema["unevaluatedProperties"]
                    ):
                        return False
                    usedProperties.add(key)

        return True
