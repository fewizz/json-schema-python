import json
import jsonschema
import os
from jsonschema.draft_2020_12 import raw

tests_files = [
    "boolean_schema",
    "minimum", "maximum", "exclusiveMaximum", "minItems", "maxItems",
    "minLength", "maxLength", "minProperties", "maxProperties", "multipleOf",
    "prefixItems",
    "const",
    "if-then-else",
    "dependentSchemas",
    "oneOf", "allOf", "anyOf",
    "pattern",
    "anchor",
    "dynamicRef",
    "unevaluatedProperties",
    "enum",
    "ref",
    "content",
    "items", "contains",
    "patternProperties", "additionalProperties", "properties",
    "required",
]

schema_by_uri = dict()

for root, dirs, files in os.walk("tests/remotes/"):
    root = root.replace("\\", "/")
    if not root.endswith("/"):
        root = f"{root}/"

    base = root.removeprefix("tests/remotes/")
    for remote_file in files:
        # if remote_file == "urn-ref-string.json":
        #    continue

        with open(f"{root}/{remote_file}") as f:
            data = json.load(f)
            uri = f"http://localhost:1234/{base}{remote_file}"
            schema_by_uri[uri] = \
                jsonschema.Schema(schema=data, uri=uri, vocabularies=raw.META)

schema_by_uri.update(raw.schema_by_uri)


def test(data):
    for global_test in data:
        schema = global_test["schema"]
        for local_test in global_test["tests"]:
            js = jsonschema.Schema(
                schema=schema,
                vocabularies=raw.META
            )
            result = js.validate(
                instance=local_test["data"],
                schema_by_uri=schema_by_uri
            )
            assert result == local_test["valid"]


for root, dirs, files in os.walk("tests/tests/draft2020-12"):
    root = root.replace("\\", "/")
    if not root.endswith("/"):
        root = f"{root}/"

    # base = root.removeprefix("tests/remotes/")
    for test_file in files:
        print(test_file)
        with open(root + test_file) as f:
            test(json.load(f))

# for test_file in tests_files:
#     print(test_file)

#     with open(f"tests/tests/draft2020-12/{test_file}.json") as f:
#         data = json.load(f)
#         test(data)


# v = jsonschema.JSONSchema(
#     schema={
#             "$schema": "https://json-schema.org/draft/2020-12/schema",
#             "$id": "https://test.json-schema.org/relative-dynamic-reference-without-bookend/root",
#             "$dynamicAnchor": "meta",
#             "type": "object",
#             "properties": {
#                 "foo": { "const": "pass" }
#             },
#             "$ref": "extended",
#             "$defs": {
#                 "extended": {
#                     "$id": "extended",
#                     "$anchor": "meta",
#                     "type": "object",
#                     "properties": {
#                         "bar": { "$ref": "bar" }
#                     }
#                 },
#                 "bar": {
#                     "$id": "bar",
#                     "type": "object",
#                     "properties": {
#                         "baz": { "$dynamicRef": "extended#meta" }
#                     }
#                 }
#             }
#         }
# )

# res = v.validate(instance={
#                     "foo": "pass",
#                     "bar": {
#                         "baz": { "foo": "fail" }
#                     }
#                 }, schema_by_uri=schema_by_uri)
# assert res is True
