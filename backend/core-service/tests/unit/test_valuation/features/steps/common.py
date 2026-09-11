
# from pytest_bdd import given, parsers

# from domains.risk.models.curve import CurveDefinition
# from shared import json_to_dataclass





# @given(parsers.parse(" I have object definition:\n{model_payload}"))
# def create_curve_definition(model_payload):
#     return json_to_dataclass.from_json(
#         CurveDefinition, model_payload, {"curve": CurveDefinition}
#     )

# import ast


# def convert_table(table_text):
#     rows = [line.strip() for line in table_text.split('\n') if line.strip()]
#     headers = [h.strip() for h in rows[0].split('|')[1:-1]]
#     data = []
#     for row in rows[1:]:
#         values = [ast.literal_eval(v.strip()) if v.strip() else None 
#                  for v in row.split('|')[1:-1]]
#         data.append(dict(zip(headers, values)))
#     return data