
# Step Definitions

import ast
import datetime
import json
from os import name
import re
from typing import Dict, Optional, Union
from pytest_bdd import given, parsers, when, then

from domains.risk.models.contexts import ValuationContextModel
from domains.risk.models.curve import Curve, CurveDefinition, CurvePoint
from domains.risk.models.pricing import CurveElement, FixedDatesAveragingRule, OffsetAveragingRule
from domains.risk.services.valuation.local.calculators.curve_calculator import CurveRefValueCalculator
from shared import json_to_dataclass
from tests.unit.test_valuation.features.steps.converters import convert_dict, convert_table, to_optional_date
from tests.unit.test_valuation.mocks.curve_definitions import CurveDefinitionDataObjectsMock
from tests.unit.test_valuation.mocks.curves import CurveDataObjectsMock

# def parse_json_docstring(text):
#     """Helper to safely parse JSON with error context."""
#     try:
#         return json.loads(text.strip('"\''))
#     except json.JSONDecodeError as e:
#         raise ValueError(f"Invalid JSON in step: {e}")

@given(
    parsers.parse('I have curve definition'),
    converters={'docstring': json.loads}      
)
def _(docstring, curve_definitions: CurveDefinitionDataObjectsMock):
    model = json_to_dataclass.from_json(
        CurveDefinition, docstring, {"curve": CurveDefinition}
    )
    curve_definitions.update(model)


@given(
    parsers.parse('the curve "{curve_name}" contains values'),
    converters={"table": convert_table}
)
def _(datatable, curve_name, curves: CurveDataObjectsMock, curve_definitions: CurveDefinitionDataObjectsMock) -> Dict:

    date_format = "%Y-%m-%d"
    # Convert Gherkin table to a dictionary
    data = {}
    headers = [h.strip() for h in datatable[0] if h.strip()]
    rows = [
        {
            "report_date": datetime.datetime.strptime(h[0], date_format).date(), 
            "observ_date": datetime.datetime.strptime(h[1], date_format).date(), 
            "value": float(h[2])
        } 
        for h in datatable[1:]
    ]

    curve_def = curve_definitions.get_first(curve_name)
    curve = Curve(curve=curve_def, values = [])
    for row in rows:
        curve.values.append(CurvePoint(observation_date=row["observ_date"], report_date=row["report_date"], value=row["value"]))

    curves.update(curve)

@when(
    parsers.parse("the curve {curve} is calculated at valuation date {val_date} and observation date {obs_date} with aggregation options {aggregation}"),
    converters={"aggregation": convert_dict, "val_date": to_optional_date, "obs_date": to_optional_date}       
)
def run_curve_calculator(curve, val_date, obs_date, aggregation, valuation_context: ValuationContextModel):
    calc = CurveRefValueCalculator()
    agg_rule = _create_aggregation(aggregation)
    curve_obj = valuation_context.data.curve_definitions.get_first(curve)
    element = CurveElement(name="A", type="curveref", curve_objects=[curve_obj], curves=[curve], aggregation=agg_rule)
    valuation_context.params.valuation_date = val_date
    valuation_context.params.observation_date = obs_date
    val = calc.execute(element, valuation_context)
    print(val.value)

@then(
    parsers.parse("the value is {expected_value}"),
    converters={"aggregation": convert_dict}    
)
def check_curve_calculator(run_curve_calculator, expected_value):
    pass


def _create_aggregation(agg) -> Optional[Union[FixedDatesAveragingRule, OffsetAveragingRule]]:
    if not agg:
        return None

    if agg["type"] == "fixed_range":
        return FixedDatesAveragingRule(**agg)
    elif agg["type"] == "offset":
        return OffsetAveragingRule(**agg)
    raise NotImplementedError()