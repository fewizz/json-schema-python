from ..vocabulary import (
    Vocabulary, Schema, LexicalScope, DynamicScope
)


class Core(Vocabulary):

    @staticmethod
    def on_schema_init(
        schema: Schema,
        schema_by_uri: dict[str, "Schema | dict | bool"],
        refs: list
    ):
        if schema.parent is None or "$id" in schema.fields:
            schema.scope = LexicalScope(root_schema=schema)
        else:
            assert schema.parent is not None
            assert schema.parent.scope is not None
            schema.scope = schema.parent.scope

        if "$id" in schema.fields:
            uri = schema.fields["$id"]
            assert isinstance(uri, str)

            # TODO this is wrong
            schemas = ("http://", "https://", "file://", "urn:")
            if not uri.startswith(schemas):
                p = schema.parent
                while True:
                    assert p is not None
                    root_uri = p.scope.root_schema.uri
                    if root_uri is not None and root_uri.startswith(schemas):
                        break
                    p = p.parent

                delimiter = ":" if root_uri.startswith("urn:") else "/"
                uri_parts = root_uri.split(delimiter)
                uri = delimiter.join(uri_parts[0:-1]) + delimiter + uri

            schema_by_uri[uri] = schema
            schema.uri = uri

        if "$anchor" in schema.fields:
            anchor = schema.fields["$anchor"]
            schema.scope.anchors[anchor] = schema

        if "$dynamicAnchor" in schema.fields:
            anchor = schema.fields["$dynamicAnchor"]
            schema.scope.dynamic_anchors[anchor] = schema

        if "$defs" in schema.fields:
            schema.fields["$defs"] = {
                name: Schema(
                    data=sub_schema,
                    parent=schema,
                    refs=refs,
                    schema_by_uri=schema_by_uri
                )
                for name, sub_schema in schema.fields["$defs"].items()
            }

        if "$vocabulary" in schema.fields:
            schema.fields["$vocabulary"] = {
                Vocabulary.by_uri[k]
                for k, v in schema.fields["$vocabulary"].items()
                if v and k in Vocabulary.by_uri
            }

    # @staticmethod
    # def on_schema_post_init(
    #     schema: Schema,
    #    schema_by_uri: dict[str, "Schema | dict | bool"]
    # ):
        if "$ref" in schema.fields:
            def f():
                uri = schema.fields["$ref"]
                ref = Core._reference(
                    schema,
                    uri,
                    schema_by_uri=schema_by_uri
                )
                assert isinstance(ref, Schema)
                schema.fields["$ref"] = ref

            refs.append(f)

        if "$dynamicRef" in schema.fields:
            def f():
                uri = schema.fields["$dynamicRef"]
                try:
                    fragment_start_index = uri.index("#")
                    fragment = uri[fragment_start_index:]
                    # uri = uri[0:fragment_start_index]
                except ValueError:
                    fragment = None

                ref = Core._reference(
                    schema,
                    uri,
                    schema_by_uri=schema_by_uri
                )

                schema.fields["$dynamicRef"] = (ref, fragment)
            refs.append(f)

    @staticmethod
    def validate(
        s: Schema,
        instance,
        scope: DynamicScope
    ):
        if "$ref" in s.fields:
            ref = s.fields["$ref"]
            assert isinstance(ref, Schema)
            if not ref.validate(
                instance=instance,
                prev_scope=scope
            ):
                return False

        if "$dynamicRef" in s.fields:
            ref, fragment = s.fields["$dynamicRef"]

            if fragment is not None:
                ref_0 = Core._fragment_reference(
                    s,
                    fragment,
                    dynamic_scope=scope
                )
                if ref_0 is not None:
                    assert isinstance(ref_0, Schema)
                    ref = ref_0

            assert isinstance(ref, Schema)

            if not ref.validate(
                instance=instance,
                prev_scope=scope
            ):
                return False

    @staticmethod
    def _reference(
        schema: Schema,
        uri: str,
        schema_by_uri: dict[str, "Schema | dict| bool"],
        scope: DynamicScope | None = None
    ) -> "Schema | None":
        try:
            fragment_start_index = uri.index("#")
            fragment = uri[fragment_start_index:]
            uri = uri[0:fragment_start_index]
        except ValueError:
            fragment = None

        next_schema = None

        if uri.startswith(("http://", "https://", "file://", "urn:")):
            next_schema = schema_by_uri[uri]
        elif len(uri) > 0:
            base = schema.scope.root_schema.uri
            assert isinstance(base, str)

            delimiter = ":" if base.startswith("urn:") else "/"
            base_parts = base.split(delimiter)

            if uri.startswith(("/", ":")):
                base = delimiter.join(base_parts[0:3])
            else:
                base = delimiter.join(base_parts[0:-1]) + delimiter
            uri = base + uri
            next_schema = schema_by_uri[uri]
        else:
            next_schema = schema.scope.root_schema

        if not isinstance(next_schema, Schema):
            if uri == schema.uri:
                next_schema = schema
            else:
                next_schema = Schema(
                    data=next_schema,
                    uri=uri,
                    schema_by_uri=schema_by_uri
                )
                schema_by_uri[uri] = next_schema

        if fragment is not None:
            scope_0 = None
            if scope is not None:
                scope_0 = DynamicScope(
                    current_lexical_scope=next_schema.scope,
                    prev_dynamic_scope=scope
                )

            next_schema = Core._fragment_reference(
                next_schema,
                fragment,
                dynamic_scope=scope_0
            )

        return next_schema

    @staticmethod
    def _fragment_reference(
        schema: Schema,
        fragment: str,
        dynamic_scope: DynamicScope | None = None,
    ) -> "Schema | None":
        assert fragment.startswith("#")
        fragment = fragment[1:]

        if dynamic_scope is None:
            if fragment in schema.scope.anchors:
                return schema.scope.anchors[fragment]
            if fragment in schema.scope.dynamic_anchors:
                return schema.scope.dynamic_anchors[fragment]
        else:
            # if fragment not in dynamic_scope.lexical_scope.dynamic_anchors:
            #    return None
            # if (
            #     fragment not in scope.scope.dynamic_anchors
            #    and fragment in scope.scope.anchors
            # ):
            #    return scope.scope.anchors[fragment]

            found = None

            sh = dynamic_scope
            while sh is not None:
                if fragment in sh.lexical_scope.anchors and found is None:
                    return sh.lexical_scope.anchors[fragment]

                if fragment in sh.lexical_scope.dynamic_anchors:
                    found = sh.lexical_scope.dynamic_anchors[fragment]

                sh = sh.prev_dynamic_scope

            return found

            # if fragment in self.scope.anchors:
            #    return self.scope.anchors[fragment]

        def reference0(
            path: list[str],
            schema: Schema | list | dict,
        ):
            if len(path) == 0:
                assert isinstance(schema, Schema)
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
                elif isinstance(schema, Schema):
                    if p in schema.fields:
                        return reference0(
                            path[1:],
                            schema=schema.fields[p]
                        )
            return None

        return reference0(fragment.split("/")[1:], schema)


Vocabulary.by_uri["https://json-schema.org/draft/2020-12/vocab/core"] = Core
