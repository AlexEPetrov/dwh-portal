import datetime
import json
import pytest

from domains.risk.models.contract import Contract
from domains.risk.models.common import ValuationParamsModel
from domains.risk.models.results import ContractValuationResult
from domains.risk.models.contexts import ValuationContextModel
from tests.unit.test_valuation.mocks.calendars import CalendarDataObjectsMock
from tests.unit.test_valuation.mocks.contracts import ContractDataObjectsMock, ValuationRunDataContextMock
from tests.unit.test_valuation.mocks.curve_definitions import CurveDefinitionDataObjectsMock
from tests.unit.test_valuation.mocks.curves import CurveDataObjectsMock


@pytest.fixture
def step_context(request):
    """Provides access to the current step's docstring"""
    def get_step_data(step_name):
        for step in request.node.steps:
            if step.name == step_name and step.doc_string:
                return json.loads(step.doc_string.strip())
        pytest.fail(f"Step '{step_name}' with docstring not found")
    return get_step_data


@pytest.fixture
def calendars():
    return CalendarDataObjectsMock()   


@pytest.fixture
def curves():
    return CurveDataObjectsMock() 


@pytest.fixture
def curve_definitions():
    return CurveDefinitionDataObjectsMock() 


# Shared fixture for simulating a contract
@pytest.fixture
def contract():
    return Contract()


@pytest.fixture
def contracts():
    return ContractDataObjectsMock()

@pytest.fixture
def valuation_data_context(curve_definitions: CurveDefinitionDataObjectsMock, curves: CurveDataObjectsMock, calendars: CalendarDataObjectsMock):
    mock = ValuationRunDataContextMock()
    mock.curve_definitions = curve_definitions
    mock.curves = curves 
    mock.calendars = calendars 
    return mock 

@pytest.fixture
def valuation_context(contract: Contract, valuation_data_context):
    context = ValuationContextModel()
    context.params = ValuationParamsModel(valuation_date=datetime.date.today(), valuation_type="eod", observation_date=datetime.date.today(), contract_slug="_", scenario_slug="_")
    context.data = valuation_data_context 
    context.contract = contract
    return context


@pytest.fixture
def valuation_result(valuation_context: ValuationContextModel):
    res = ContractValuationResult()
    res.pricing_uom = valuation_context.contract.pricing_uom
    res.valuation_date = valuation_context.params.valuation_date
    res.observation_date = valuation_context.params.valuation_date
    return res