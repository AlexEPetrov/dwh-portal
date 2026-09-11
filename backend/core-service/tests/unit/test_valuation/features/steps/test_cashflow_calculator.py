import datetime

from pytest_bdd import given, parsers, scenarios, then, when
from tests.unit.test_valuation.features.steps.converters import (
    to_optional_date,
    to_optional_float,
    to_optional_int,
)
from tests.unit.test_valuation.mocks.calendars import CalendarDataObjectsMock

from domains.risk.models.contexts import ValuationContextModel
from domains.risk.models.contract import (
    Contract,
    PaymentAmountType,
    PaymentTerm,
    PaymentTermAnchorDate,
)
from domains.risk.models.pricing import OffsetUnit
from domains.risk.models.results import ContractValuationResult
from domains.risk.services.valuation.local.calculators.cashflow_calculator import (
    CashflowCalculator,
)

# Load the feature file
scenarios("./../cashflow_calculator.feature")


# Step Definitions


@given(parsers.parse("I have a contract with pricing uom {pricing_uom}"))
def contract_created(contract: Contract, pricing_uom: str):
    contract.pricing_uom = pricing_uom.replace('"', "")
    contract.payment_terms = []
    return contract


@given(parsers.parse("the contract payment period is {payment_period}"))
def contract_payment_period(contract: Contract, payment_period):
    # Payment period is stored in each PaymentTerm itself; scenarios currently use "month".
    _ = payment_period
    return contract


@given(
    parsers.parse(
        "the contract payment schedule contains prepayment at "
        "{prep_offset}, {prep_offset_unit}, {prep_pcnt}, {prep_value}"
    ),
    converters={
        "prep_offset": to_optional_int,
        "prep_pcnt": to_optional_float,
        "prep_value": to_optional_float,
    },
)
def contract_prepayment(contract: Contract, prep_offset, prep_offset_unit, prep_pcnt, prep_value):
    amount = prep_value if prep_value else prep_pcnt
    if amount:
        contract.payment_terms.append(
            PaymentTerm(
                payment_period="month",
                date_offset=prep_offset if prep_offset else None,
                date_offset_unit=OffsetUnit(prep_offset_unit),
                amount=amount,
                amount_type=(
                    PaymentAmountType.FIXED if prep_value else PaymentAmountType.PERCENTAGE
                ),
                anchor_date=PaymentTermAnchorDate.PAYMENT_PERIOD_START,
            )
        )
    return contract


@given(
    parsers.parse(
        "the contract payment schedule contains final payment at "
        "{final_offset}, {final_offset_unit}, {final_pcnt}, {final_value}"
    ),
    converters={
        "final_offset": to_optional_int,
        "final_pcnt": to_optional_float,
        "final_value": to_optional_float,
    },
)
def contract_final_payment(
    contract: Contract, final_offset, final_offset_unit, final_pcnt, final_value
):
    amount = float(final_value) if final_value else float(final_pcnt) if final_pcnt else None
    if amount:
        contract.payment_terms.append(
            PaymentTerm(
                payment_period="month",
                date_offset=int(final_offset) if final_offset else None,
                date_offset_unit=OffsetUnit(final_offset_unit),
                amount=amount,
                amount_type=(
                    PaymentAmountType.FIXED if final_value else PaymentAmountType.PERCENTAGE
                ),
                anchor_date=PaymentTermAnchorDate.PAYMENT_PERIOD_END,
            )
        )
    return contract


@when(
    parsers.parse("the cashflow is calculated at valuation date {val_date} with value {value}"),
    converters={"val_date": to_optional_date, "value": to_optional_float},
)
def contract_valuation(
    valuation_context: ValuationContextModel,
    valuation_result: ContractValuationResult,
    calendars: CalendarDataObjectsMock,
    val_date,
    value,
):
    valuation_context.params.valuation_date = val_date
    valuation_context.valuation_month = datetime.date(val_date.year, val_date.month, 1)
    valuation_result.valuation_date = val_date
    valuation_result.value = value
    calculator = CashflowCalculator(calendars, "default")
    valuation_result.payments = calculator.execute(valuation_context, valuation_result)


@then(
    parsers.parse(
        "the valuation result should have prepayment at date {expected_prep_date} for amount {expected_prep_value}"
    ),
    converters={
        "expected_prep_date": to_optional_date,
        "expected_prep_value": to_optional_float,
    },
)
def has_valid_prepayment(
    valuation_result: ContractValuationResult, expected_prep_date, expected_prep_value
):
    found = False
    for payment in valuation_result.payments:
        if (
            payment.amount == expected_prep_value
            and payment.payment_date == expected_prep_date
            and payment.payment_type == "month prepayment"
        ):
            found = True
            break

    if not found:
        assert expected_prep_value is None, "expected prepaymet not found"


@then(
    parsers.parse(
        "the valuation result should have final payment at date {expected_final_date} for amount {expected_final_value}"
    ),
    converters={
        "expected_final_date": to_optional_date,
        "expected_final_value": to_optional_float,
    },
)
def has_valid_final_payment(
    valuation_result: ContractValuationResult, expected_final_date, expected_final_value
):
    found = False
    for payment in valuation_result.payments:
        if (
            payment.amount == expected_final_value
            and payment.payment_date == expected_final_date
            and payment.payment_type == "month final"
        ):
            found = True
            break

    if not found:
        assert expected_final_value is None, "expected final paymet not found"
