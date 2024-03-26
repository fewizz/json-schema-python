import json
import jsonschema
import os
from jsonschema.draft_2020_12 import raw
import copy

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
            schema_by_uri[uri] = data
            # jsonschema.Schema(
            # 	data=data,
            # 	uri=uri,
            # 	schema=raw.META,
            # 	schema_by_uri=copy.deepcopy(schema_by_uri)
            # )

schema_by_uri.update(raw.schema_by_uri)


def test(data):
    for global_test in data:
        schema = global_test["schema"]
        for local_test in global_test["tests"]:
            js = jsonschema.Schema(
                data=schema,
                schema_by_uri=schema_by_uri
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


v = jsonschema.Schema(
    data={
            "$id": "https://schema/using/no/validation",
            "$schema": "http://localhost:1234/draft2020-12/metaschema-no-validation.json",
            "properties": {
                "badProperty": False,
                "numberProperty": {
                    "minimum": 10
                }
            }
        },
    schema_by_uri=schema_by_uri
)

res = v.validate(instance={
                    "badProperty": "this property should not exist"
                }, schema_by_uri={})
assert res is False
