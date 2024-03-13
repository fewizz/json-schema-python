import json
import jsonschema
import os
from jsonschema import schema_2020_12

tests_files = [
    # "type", "boolean_schema", "properties", "required",
    # "items",
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
    "ref",
    "items", "contains",
    "patternProperties", "additionalProperties", "properties",
    "required", "enum",
]

schema_by_uri = dict()

for root, dirs, files in os.walk("tests/remotes/"):
    root = root.replace("\\", "/")
    if not root.endswith("/"):
        root = f"{root}/"

    base = root.removeprefix("tests/remotes/")
    for remote_file in files:
        with open(f"{root}/{remote_file}") as f:
            data = json.load(f)
            schema_by_uri[f"http://localhost:1234/{base}{remote_file}"] = data

# for test_file in tests_files:
#     print(test_file)

#     with open(f"tests/tests/draft2020-12/{test_file}.json") as f:
#         data = json.load(f)

#         for global_test in data:
#             schema = global_test["schema"]
#             for local_test in global_test["tests"]:
#                 js = jsonschema.JSONSchema(
#                     schema=schema,
#                     schema_by_uri=schema_2020_12.schema_by_uri | schema_by_uri
#                 )
#                 result = js.validate(instance=local_test["data"])
#                 assert result == local_test["valid"]


v = jsonschema.JSONSchema(
    schema={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://test.json-schema.org/dynamic-resolution-with-intermediate-scopes/root",
            "$ref": "intermediate-scope",
            "$defs": {
                "foo": {
                    "$dynamicAnchor": "items",
                    "type": "string"
                },
                "intermediate-scope": {
                    "$id": "intermediate-scope",
                    "$ref": "list"
                },
                "list": {
                    "$id": "list",
                    "type": "array",
                    "items": { "$dynamicRef": "#items" },
                    "$defs": {
                      "items": {
                          "$comment": "This is only needed to satisfy the bookending requirement",
                          "$dynamicAnchor": "items"
                      }
                    }
                }
            }
        },
    schema_by_uri=schema_2020_12.schema_by_uri | schema_by_uri
)

res = v.validate(instance=["foo", 42])
assert res is False