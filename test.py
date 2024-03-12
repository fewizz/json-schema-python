import json
import jsonschema
from jsonschema import schema_2020_12

tests_files = [
    "boolean_schema",
    "type", "minimum", "maximum", "exclusiveMaximum", "minItems", "maxItems",
    "minLength", "maxLength", "minProperties", "maxProperties", "multipleOf",
    "prefixItems",
    "if-then-else",
    "dependentSchemas",
    "dynamicRef",
    "unevaluatedProperties",
    "ref",
    "items", "contains",
    "patternProperties", "additionalProperties", "properties",
    "required", "enum", "const",
    "oneOf", "allOf", "anyOf"
]

for test_file in tests_files:
    print(test_file)

    with open(f"tests/tests/draft2020-12/{test_file}.json") as f:
        data = json.load(f)

        for global_test in data:
            schema = global_test["schema"]
            for local_test in global_test["tests"]:
                result = jsonschema.Validator(
                    schema=schema,
                    content_by_uid=schema_2020_12.content_by_uri
                ).validate(
                    instance=local_test["data"]
                )
                assert result == local_test["valid"]


# v = jsonschema.Validator(
#     schema={
#         "$schema": "https://json-schema.org/draft/2020-12/schema",
#         "type": "object",
#         "properties": {
#             "foo": { "type": "string" }
#         },
#         "dependentSchemas": {
#             "foo": {
#                 "properties": {
#                     "bar": { "const": "bar" }
#                 },
#                 "required": ["bar"]
#             }
#         },
#         "unevaluatedProperties": False
#     },
#     content_by_uid=schema_2020_12.content_by_uri
# )

# assert v.validate(instance={
#     "foo": "foo",
#     "bar": "bar"
# }) is True


# v.validate(instance={
#     "bar": "bar"
# }) is False