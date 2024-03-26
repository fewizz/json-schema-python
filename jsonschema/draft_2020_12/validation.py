import numbers
import re
import itertools
import math
from ..vocabulary import Vocabulary, Schema, DynamicScope


class Validation(Vocabulary):

    @staticmethod
    def validate(
        s: Schema,
        instance,
        scope: DynamicScope
    ):
        if "type" in s.fields:
            _type = s.fields["type"]
            if isinstance(_type, list):
                if not any(Validation._check_type(t, instance) for t in _type):
                    return False
            else:
                if not Validation._check_type(_type, instance):
                    return False

        if "const" in s.fields:
            if not Validation._compare(instance, s.fields["const"]):
                return False

        if "enum" in s.fields:
            enum: list = s.fields["enum"]
            if instance not in enum:
                return False
            val = enum[enum.index(instance)]

            if not Validation._compare(instance, val):
                return False

        if isinstance(instance, numbers.Real):
            if "minimum" in s.fields and instance < s.fields["minimum"]:
                return False

            if "maximum" in s.fields and instance > s.fields["maximum"]:
                return False

            if (
                "exclusiveMaximum" in s.fields
                and instance >= s.fields["exclusiveMaximum"]
            ):
                return False

            if (
                "exclusiveMinimum" in s.fields
                and instance <= s.fields["exclusiveMinimum"]
            ):
                return False

            if "multipleOf" in s.fields:
                multiple = s.fields["multipleOf"]
                mod = instance % multiple
                if not (
                    mod == 0 or (multiple - mod) < 0.00001
                ):
                    return False

        if isinstance(instance, str):
            if (
                "minLength" in s.fields
                and len(instance) < s.fields["minLength"]
            ):
                return False

            if (
                "maxLength" in s.fields
                and len(instance) > s.fields["maxLength"]
            ):
                return False

            if (
                "pattern" in s.fields
                and not re.search(
                    pattern=s.fields["pattern"],
                    string=instance
                )
            ):
                return False

        if isinstance(instance, list):
            if (
                "minItems" in s.fields
                and len(instance) < s.fields["minItems"]
            ):
                return False

            if (
                "maxItems" in s.fields
                and len(instance) > s.fields["maxItems"]
            ):
                return False

            if "uniqueItems" in s.fields and s.fields["uniqueItems"]:
                for a, b in itertools.combinations(instance, 2):
                    if Validation._compare(a, b):
                        return False

        if isinstance(instance, dict):
            if (
                "minProperties" in s.fields
                and len(instance) < s.fields["minProperties"]
            ):
                return False

            if (
                "maxProperties" in s.fields
                and len(instance) > s.fields["maxProperties"]
            ):
                return False

            if "required" in s.fields:
                for key in s.fields["required"]:
                    if key not in instance:
                        return False

            if "dependentRequired" in s.fields:
                for key, required in s.fields["dependentRequired"].items():
                    if key in instance:
                        for req in required:
                            if req not in instance:
                                return False

    @staticmethod
    def _check_type(type: str, instance):
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
                if not Validation._compare(aa, bb):
                    return False
            return True
        elif isinstance(a, dict) and isinstance(b, dict):
            if len(a) != len(b):
                return False
            for key in a:
                if key not in b or not Validation._compare(a[key], b[key]):
                    return False
            return True
        else:
            return a == b


Vocabulary.by_uri[
    "https://json-schema.org/draft/2020-12/vocab/validation"
] = Validation
