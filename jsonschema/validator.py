from typing import Any
import numbers
import math
import re
import sys
import itertools


class Scope:

    def __init__(
        self,
        schema: "JSONSchema",
        schema_by_uri: dict[str, "JSONSchema"]
    ):
        self.schema = schema
        self.anchors = dict[str, "JSONSchema"]()
        self.dynamic_anchors = dict[str, "JSONSchema"]()
        self.schema_by_uri = schema_by_uri


class ScopeHandle:

    def __init__(
        self,
        current_scope: Scope,
        previous_scope_handle: "ScopeHandle | None"
    ):
        self.current_scope = current_scope
        self.previous_scope_handle = previous_scope_handle


class JSONSchema:

    def __init__(
        self,
        schema: dict | bool,
        parent: "JSONSchema | None" = None,
        uri: str | None = None
    ):
        self.parent = parent

        if isinstance(schema, bool):
            if schema:
                schema = {}
            else:
                schema = {"not": {}}

        if parent is None or "$id" in schema:
            if parent is None:
                schema_by_uri = dict[str, JSONSchema]()
            else:
                schema_by_uri = parent.scope.schema_by_uri
            self.scope = Scope(self, schema_by_uri=schema_by_uri)
        else:
            assert parent is not None
            self.scope = parent.scope

        self.uri = uri

        if "$id" in schema:
            uri = schema["$id"]
            assert isinstance(uri, str)

            # TODO this is wrong
            schemas = ("http://", "https://", "file://", "urn:")
            if not uri.startswith(schemas):
                p = parent
                while True:
                    assert p is not None
                    root_uri = p.scope.schema.uri
                    if root_uri is not None and root_uri.startswith(schemas):
                        break
                    p = p.parent

                delimiter = ":" if root_uri.startswith("urn:") else "/"
                uri_parts = root_uri.split(delimiter)
                uri = delimiter.join(uri_parts[0:-1]) + delimiter + uri

            self.scope.schema_by_uri[uri] = self
            self.uri = uri

        if "$anchor" in schema:
            anchor = schema["$anchor"]
            self.scope.anchors[anchor] = self

        if "$dynamicAnchor" in schema:
            anchor = schema["$dynamicAnchor"]
            self.scope.dynamic_anchors[anchor] = self

        self.fields = dict[str, Any]()

        for k, v in schema.items():
            if k in (
                "if", "then", "else", "not", "contains",
                "additionalProperties", "items", "unevaluatedItems",
                "unevaluatedProperties", "propertyNames"
            ):
                self.fields[k] = JSONSchema(
                    schema=v,
                    parent=self
                )
            elif k in (
                "allOf", "anyOf", "oneOf", "prefixItems"
            ):
                self.fields[k] = [
                    JSONSchema(
                        schema=sub_schema,
                        parent=self
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
                        parent=self
                    )
                    for name, sub_schema in v.items()
                }
            else:
                self.fields[k] = v

    @staticmethod
    def _mix_evaluated(func):
        def _fun(
            self,
            instance,
            schema_by_uri: dict[str, "JSONSchema"],
            evaluated_props: set[str] | None = None,
            evaluated_items: set[int] | None = None,
            previous_scope_handle: ScopeHandle | None = None
        ):
            evaluated_props_0 = set[str]()
            evaluated_items_0 = set[int]()
            result: bool = func(
               self,
               instance,
               schema_by_uri,
               evaluated_props_0,
               evaluated_items_0,
               previous_scope_handle
            )
            if evaluated_props is not None:
                evaluated_props.update(evaluated_props_0)
            if evaluated_items is not None:
                evaluated_items.update(evaluated_items_0)
                # for i in evaluated_items_0:
                #    if i not in evaluated_items:
                #        evaluated_items.append(i)
            return result
        return _fun

    @_mix_evaluated
    def validate(
        self,
        instance,
        schema_by_uri: dict[str, "JSONSchema"],
        evaluated_props: set[str] | None = None,
        evaluated_items: set[int] | None = None,
        previous_scope_handle: ScopeHandle | None = None
    ):
        assert evaluated_props is not None
        assert evaluated_items is not None

        scope_handle = ScopeHandle(
            current_scope=self.scope,
            previous_scope_handle=previous_scope_handle
        )

        if "$ref" in self.fields:
            uri = self.fields["$ref"]
            ref = self._reference(
                uri,
                schema_by_uri=schema_by_uri,
                dynamic=False,
                scope_handle=scope_handle
            )
            assert isinstance(ref, JSONSchema)
            if not ref.validate(
                instance=instance,
                schema_by_uri=schema_by_uri,
                evaluated_props=evaluated_props,
                evaluated_items=evaluated_items,
                previous_scope_handle=scope_handle
            ):
                return False

        if "$dynamicRef" in self.fields:
            uri = self.fields["$dynamicRef"]
            ref = self._reference(
                uri,
                schema_by_uri=schema_by_uri,
                dynamic=True,
                scope_handle=scope_handle
            )
            assert isinstance(ref, JSONSchema)
            if not ref.validate(
                instance=instance,
                schema_by_uri=schema_by_uri,
                evaluated_props=evaluated_props,
                evaluated_items=evaluated_items,
                previous_scope_handle=scope_handle
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
            if sub.validate(
                instance,
                schema_by_uri=schema_by_uri,
                previous_scope_handle=scope_handle
            ):
                return False

        if "const" in self.fields:
            if not JSONSchema._compare(instance, self.fields["const"]):
                return False

        if "enum" in self.fields:
            enum: list = self.fields["enum"]
            if instance not in enum:
                return False
            val = enum[enum.index(instance)]

            if not JSONSchema._compare(instance, val):
                return False

        if "oneOf" in self.fields:
            count = 0
            for sub in self.fields["oneOf"]:
                assert isinstance(sub, JSONSchema)
                # locally_evaluated_properties_0 = set[str]()
                if sub.validate(
                    instance=instance,
                    schema_by_uri=schema_by_uri,
                    evaluated_props=evaluated_props,
                    evaluated_items=evaluated_items,
                    previous_scope_handle=scope_handle
                ):
                    count += 1
                # if count == 1:
                #    locally_evaluated_properties.update(
                #        locally_evaluated_properties
                #    )
            if count != 1:
                return False

        if "allOf" in self.fields:
            count = 0
            subs = self.fields["allOf"]
            for sub in subs:
                assert isinstance(sub, JSONSchema)
                # locally_evaluated_properties = set[str]()
                if sub.validate(
                    instance=instance,
                    schema_by_uri=schema_by_uri,
                    evaluated_props=evaluated_props,
                    evaluated_items=evaluated_items,
                    previous_scope_handle=scope_handle
                ):
                    count += 1
                # evaluated_properties.update(locally_evaluated_properties)
            if count != len(subs):
                return False

        if "anyOf" in self.fields:
            count = 0
            for sub in self.fields["anyOf"]:
                assert isinstance(sub, JSONSchema)
                # locally_evaluated_properties_0 = set[str]()
                if sub.validate(
                    instance=instance,
                    schema_by_uri=schema_by_uri,
                    evaluated_props=evaluated_props,
                    evaluated_items=evaluated_items,
                    previous_scope_handle=scope_handle
                ):
                    count += 1
            if count == 0:
                return False

        if "if" in self.fields:
            sub = self.fields["if"]
            assert isinstance(sub, JSONSchema)
            result = sub.validate(
                instance=instance,
                schema_by_uri=schema_by_uri,
                evaluated_props=evaluated_props,
                evaluated_items=evaluated_items,
                previous_scope_handle=scope_handle
            )
            if result and "then" in self.fields:
                sub = self.fields["then"]
                assert isinstance(sub, JSONSchema)
                if not sub.validate(
                    instance=instance,
                    schema_by_uri=schema_by_uri,
                    evaluated_props=evaluated_props,
                    evaluated_items=evaluated_items,
                    previous_scope_handle=scope_handle
                ):
                    return False
                else:
                    pass
            if not result and "else" in self.fields:
                sub = self.fields["else"]
                assert isinstance(sub, JSONSchema)
                if not sub.validate(
                    instance=instance,
                    schema_by_uri=schema_by_uri,
                    evaluated_props=evaluated_props,
                    evaluated_items=evaluated_items,
                    previous_scope_handle=scope_handle
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

            if (
                "exclusiveMinimum" in self.fields
                and instance <= self.fields["exclusiveMinimum"]
            ):
                return False

            if "multipleOf" in self.fields:
                multiple = self.fields["multipleOf"]
                mod = instance % multiple
                if not (
                    mod == 0 or (multiple - mod) < 0.00001
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

        if isinstance(instance, list):
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

            if "uniqueItems" in self.fields and self.fields["uniqueItems"]:
                for a, b in itertools.combinations(instance, 2):
                    if JSONSchema._compare(a, b):
                        return False

            locally_evaluated_items = set[int]()

            if "prefixItems" in self.fields:
                for index, sub in enumerate(self.fields["prefixItems"]):
                    assert isinstance(sub, JSONSchema)
                    if index >= len(instance):
                        break
                    item = instance[index]
                    if not sub.validate(
                        item,
                        schema_by_uri=schema_by_uri,
                        evaluated_items=evaluated_items,
                        previous_scope_handle=scope_handle
                    ):
                        return False
                    locally_evaluated_items.add(index)

            if "items" in self.fields:
                sub = self.fields["items"]
                assert isinstance(sub, JSONSchema)
                initial_index = 0
                if "prefixItems" in self.fields:
                    initial_index = len(self.fields["prefixItems"])

                if initial_index < len(instance):
                    for index, item in enumerate(
                        instance[initial_index:],
                        start=initial_index
                    ):
                        if not sub.validate(
                            item,
                            schema_by_uri=schema_by_uri,
                            evaluated_items=evaluated_items,
                            previous_scope_handle=scope_handle
                        ):
                            return False
                        # elif item not in evaluated_items:
                        #    locally_evaluated_items.append(item)
                        locally_evaluated_items.add(index)

            if "contains" in self.fields:
                sub = self.fields["contains"]
                assert isinstance(sub, JSONSchema)

                min_contains: int = self.fields.get("minContains", 1)
                max_contains: int = self.fields.get("maxContains", sys.maxsize)

                count = 0
                for index, i in enumerate(instance):
                    if sub.validate(
                        instance=i,
                        schema_by_uri=schema_by_uri,
                        previous_scope_handle=scope_handle
                    ):
                        count += 1
                        locally_evaluated_items.add(index)

                if count < min_contains or count > max_contains:
                    return False

            evaluated_items.update(locally_evaluated_items)

            if "unevaluatedItems" in self.fields:
                sub = self.fields["unevaluatedItems"]
                assert isinstance(sub, JSONSchema)

                for index, item in enumerate(instance):
                    if index not in evaluated_items:
                        if not sub.validate(
                            instance=item,
                            schema_by_uri=schema_by_uri,
                            previous_scope_handle=scope_handle,
                        ):
                            return False
                        evaluated_items.add(index)

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

            if "dependentRequired" in self.fields:
                for key, required in self.fields["dependentRequired"].items():
                    if key in instance:
                        for req in required:
                            if req not in instance:
                                return False

            if "dependentSchemas" in self.fields:
                for prop_name, sub in self.fields["dependentSchemas"].items():
                    assert isinstance(sub, JSONSchema)
                    valid = True
                    if prop_name in instance:
                        valid &= sub.validate(
                            instance=instance,
                            schema_by_uri=schema_by_uri,
                            evaluated_props=evaluated_props,
                            previous_scope_handle=scope_handle
                        )
                    if not valid:
                        return False

            if "propertyNames" in self.fields:
                sub = self.fields["propertyNames"]
                assert isinstance(sub, JSONSchema)

                for prop_name in instance.keys():
                    if not sub.validate(
                        instance=prop_name,
                        schema_by_uri=schema_by_uri,
                        previous_scope_handle=previous_scope_handle
                    ):
                        return False

            locally_evaluated_props = set[str]()

            if "patternProperties" in self.fields:
                for key in instance:
                    props: dict[str, JSONSchema] \
                        = self.fields["patternProperties"]
                    for pattern, sub in props.items():
                        assert isinstance(sub, JSONSchema)
                        if re.search(
                            pattern=pattern,
                            string=key
                        ):
                            if not sub.validate(
                                instance=instance[key],
                                schema_by_uri=schema_by_uri,
                                previous_scope_handle=scope_handle
                            ):
                                return False
                            locally_evaluated_props.add(key)

            if "properties" in self.fields:
                for key, sub in self.fields["properties"].items():
                    assert isinstance(sub, JSONSchema)
                    if key in instance:
                        if not sub.validate(
                            instance=instance[key],
                            schema_by_uri=schema_by_uri,
                            previous_scope_handle=scope_handle
                        ):
                            return False
                        locally_evaluated_props.add(key)

            if "additionalProperties" in self.fields:
                sub = self.fields["additionalProperties"]
                assert isinstance(sub, JSONSchema)
                for key in instance:
                    if key not in locally_evaluated_props:
                        if not sub.validate(
                            instance=instance[key],
                            schema_by_uri=schema_by_uri,
                            previous_scope_handle=scope_handle
                        ):
                            return False
                        locally_evaluated_props.add(key)

            evaluated_props.update(locally_evaluated_props)

            if "unevaluatedProperties" in self.fields:
                sub = self.fields["unevaluatedProperties"]
                assert isinstance(sub, JSONSchema)

                for key in instance:
                    if key not in evaluated_props:
                        if not sub.validate(
                            instance=instance[key],
                            schema_by_uri=schema_by_uri,
                            previous_scope_handle=scope_handle
                        ):
                            return False
                        evaluated_props.add(key)

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

    def _reference(
        self,
        uri: str,
        dynamic: bool,
        schema_by_uri: dict[str, "JSONSchema"],
        scope_handle: ScopeHandle
    ) -> "JSONSchema | None":
        try:
            fragment_start_index = uri.index("#")
            fragment = uri[fragment_start_index:]
            uri = uri[0:fragment_start_index]
        except ValueError:
            fragment = None

        merged = self.scope.schema_by_uri | schema_by_uri

        schema = None

        if uri.startswith(("http://", "https://", "file://", "urn:")):
            schema = merged[uri]
        elif len(uri) > 0:
            base = self.scope.schema.uri
            assert isinstance(base, str)

            delimiter = ":" if base.startswith("urn:") else "/"
            base_parts = base.split(delimiter)

            if uri.startswith(("/", ":")):
                base = delimiter.join(base_parts[0:3])
            else:
                base = delimiter.join(base_parts[0:-1]) + delimiter

            schema = merged[base + uri]
        else:
            schema = self.scope.schema

        if fragment is not None:
            schema = schema._fragment_reference(
                fragment,
                dynamic=dynamic,
                scope_handle=ScopeHandle(
                    current_scope=schema.scope,
                    previous_scope_handle=scope_handle
                )
            )

        return schema

    def _fragment_reference(
        self,
        fragment: str,
        dynamic: bool,
        scope_handle: ScopeHandle
    ) -> "JSONSchema | None":
        assert fragment.startswith("#")
        fragment = fragment[1:]

        if not dynamic:
            if fragment in self.scope.anchors:
                return self.scope.anchors[fragment]
            if fragment in self.scope.dynamic_anchors:
                return self.scope.dynamic_anchors[fragment]
        else:
            if (
                fragment not in scope_handle.current_scope.dynamic_anchors
                and fragment in scope_handle.current_scope.anchors
            ):
                return scope_handle.current_scope.anchors[fragment]

            found = None

            sh = scope_handle
            while sh is not None:
                if fragment in sh.current_scope.dynamic_anchors:
                    found = sh.current_scope.dynamic_anchors[fragment]

                sh = sh.previous_scope_handle

            if found is not None:
                return found

            # if fragment in self.scope.anchors:
            #    return self.scope.anchors[fragment]

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


# class Validator:

    
#     def validate(
#         self, instance,
#         schema: dict | bool | None = None,
#         usedProperties: set[str] | None = None
#     ):
#         if schema is None:
#             schema = self.schema
#         if usedProperties is None:
#             usedProperties = set()

#         if schema is True:
#             return True
#         if schema is False:
#             return False


#         return True
