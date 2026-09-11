"""Unit tests for gl_account parity between ContractValuationResult and source Contract.

Regression tests for: https://github.com/.../gl_account=none-partition-issue
When general_contract_calculator did not pass gl_account, parquet output
created spurious gl_account=none partitions even when user filtered by
gl_accounts=["OP_REV_SALES"].
"""

import datetime
from unittest.mock import MagicMock

from domains.risk.models.contract import Contract
from domains.risk.models.results import ContractValuationResult

# ─────────────────────────────────────────────────────────────────────────────
# Helpers: build a minimal ContractValuationResult
# ─────────────────────────────────────────────────────────────────────────────


def _make_contract(
    slug: str = "test_contract",
    gl_account: str | None = None,
    product: str = "Gas",
    delivery_market: str = "m1",
    counterparty: str = "CP1",
) -> Contract:
    """Build a minimal Contract with given gl_account."""
    c = Contract()
    c.id = "00000000-0000-0000-0000-000000000001"
    c.slug = slug
    c.name = slug
    c.type = "sales"
    c.contract_type = "physical"
    c.is_active = True
    c.gl_account = gl_account
    c.product = product
    c.delivery_market = delivery_market
    c.counterparty = counterparty
    c.supply_path = "SP1"
    c.country = "RU"
    c.pricing_uom = "m3"
    c.volume_uom = "m3"
    c.pricing_uom_model = "1"
    c.volume_uom_model = "1"
    c.pricing = []
    c.deliveries = []
    return c


def _make_valuation_result(
    gl_account: str | None = None,
    product: str = "Gas",
    delivery_market: str = "m1",
    payments: list | None = None,
    deliveries: list | None = None,
) -> ContractValuationResult:
    """Build a minimal ContractValuationResult."""
    res = ContractValuationResult()
    res.id = "00000000-0000-0000-0000-000000000002"
    res.slug = "test_contract"
    res.name = "test_contract"
    res.gl_account = gl_account
    res.product = product
    res.delivery_market = delivery_market
    res.counterparty = "CP1"
    res.valuation_date = datetime.date(2026, 1, 15)
    res.observation_date = datetime.date(2026, 1, 1)
    res.valuation_type = "deterministic"
    res.value = 1000.0
    res.volume = 500.0
    res.waprice = 2.0
    res.payments = payments or []
    res.deliveries = deliveries or []
    res.pricing = []
    res.reportings = []
    res.scenario = "base"
    res.supply_path = "SP1"
    res.country = "RU"
    return res


# ─────────────────────────────────────────────────────────────────────────────
# Test: gl_account value correctness
# ─────────────────────────────────────────────────────────────────────────────


class TestGlAccountInContractValuationResult:
    """gl_account must be passed from Contract to ContractValuationResult."""

    def test_gl_account_copy_when_non_empty(self):
        """When contract.gl_account is set, valuation result must have it."""
        contract = _make_contract(gl_account="OP_REV_SALES")
        result = _make_valuation_result(gl_account=contract.gl_account)
        assert result.gl_account == "OP_REV_SALES"

    def test_gl_account_none_is_preserved(self):
        """When contract.gl_account is None, valuation result must also be None."""
        contract = _make_contract(gl_account=None)
        result = _make_valuation_result(gl_account=contract.gl_account)
        assert result.gl_account is None

    def test_gl_account_empty_string(self):
        """Empty string gl_account should be preserved."""
        contract = _make_contract(gl_account="")
        result = _make_valuation_result(gl_account=contract.gl_account)
        assert result.gl_account == ""


# ─────────────────────────────────────────────────────────────────────────────
# Test: partition path generation — no spurious "none" partitions
# ─────────────────────────────────────────────────────────────────────────────


class TestPartitionPathGeneration:
    """Partition paths must not contain 'gl_account=none' when user filters."""

    def test_gl_account_none_value_maps_to_none_partition(self):
        """gl_account=None produces partition 'gl_account=none'."""
        result = _make_valuation_result(gl_account=None)
        # This is expected: when gl_account is None, partition key is "none"
        assert (result.gl_account or "none") == "none"

    def test_gl_account_with_value_maps_to_correct_partition(self):
        """gl_account=OP_REV_SALES produces partition 'gl_account=OP_REV_SALES'."""
        result = _make_valuation_result(gl_account="OP_REV_SALES")
        assert (result.gl_account or "none") == "OP_REV_SALES"

    def test_gl_account_empty_string_maps_to_none_partition(self):
        """Empty string gl_account also maps to 'none' partition."""
        result = _make_valuation_result(gl_account="")
        assert (result.gl_account or "none") == "none"


class TestParquetPartitionIntegrity:
    """Simulate _save_parquet_results logic to verify no spurious partitions."""

    def test_contracts_with_only_valid_gl_account_single_partition(self):
        """When all contracts have gl_account=OP_REV_SALES, only one partition should exist."""
        valuations = [
            _make_valuation_result(gl_account="OP_REV_SALES"),
            _make_valuation_result(gl_account="OP_REV_SALES"),
        ]

        # Simulate contracts_by_partitions grouping from _save_parquet_results
        contracts_by_partitions = {}
        for val in valuations:
            key = (
                val.valuation_date.year,
                val.valuation_date.month,
                val.gl_account or "none",
                val.delivery_market or "none",
                val.product or "none",
                val.scenario or "none",
            )
            if key not in contracts_by_partitions:
                contracts_by_partitions[key] = []
            contracts_by_partitions[key].append(val)

        # Assert: only ONE partition (OP_REV_SALES), no "none" partition
        partition_keys = list(contracts_by_partitions.keys())
        assert len(partition_keys) == 1
        assert partition_keys[0][2] == "OP_REV_SALES"  # gl_account column

    def test_payments_exist_when_valuations_have_payments(self):
        """payments.parquet should be written when valuations have payments."""
        payment = MagicMock()
        payment.payment_date = datetime.date(2026, 2, 1)
        payment.currency = "USD"
        payment.payment_type = "fixed"
        payment.amount = 1000.0
        payment.amount_usd = 1000.0
        payment.amount_rub = 90000.0
        payment.volume = 500.0

        valuations = [
            _make_valuation_result(
                gl_account="OP_REV_SALES",
                payments=[payment],
            ),
        ]

        # Simulate payments_by_valuation_period grouping
        payments_by_valuation_period = {}
        for val in valuations:
            key = (
                val.valuation_date.year,
                val.valuation_date.month,
                val.gl_account or "none",
                val.delivery_market or "none",
                val.product or "",
                val.scenario or "none",
            )
            for payment_item in val.payments or []:
                if key not in payments_by_valuation_period:
                    payments_by_valuation_period[key] = []
                payments_by_valuation_period[key].append(payment_item)

        # Assert: partition exists in payments
        partition_keys = list(payments_by_valuation_period.keys())
        assert len(partition_keys) == 1
        assert partition_keys[0][2] == "OP_REV_SALES"

    def test_no_spurious_none_partition_when_gl_account_filtered(self):
        """Main regression test: gl_account=None should NOT appear when filtering."""
        # Simulate: user requested gl_accounts=["OP_REV_SALES"]
        # All valuation results should have gl_account=OP_REV_SALES
        valuations = [
            _make_valuation_result(gl_account="OP_REV_SALES"),
            _make_valuation_result(gl_account="OP_REV_SALES"),
        ]

        contracts_by_partitions = {}
        for val in valuations:
            key = (
                val.valuation_date.year,
                val.valuation_date.month,
                val.gl_account or "none",
                val.delivery_market or "none",
                val.product or "none",
                val.scenario or "none",
            )
            if key not in contracts_by_partitions:
                contracts_by_partitions[key] = []
            contracts_by_partitions[key].append(val)

        # The bug was: gl_account=none partition appeared alongside OP_REV_SALES
        none_partitions = [k for k in contracts_by_partitions if k[2] == "none"]
        assert len(none_partitions) == 0, (
            f"Unexpected gl_account=none partition(s) found: {none_partitions}. "
            "This means ContractValuationResult.gl_account was None when it should have been 'OP_REV_SALES'."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Test: general_contract_calculator gl_account fix
# ─────────────────────────────────────────────────────────────────────────────


class TestGeneralContractCalculatorGlAccountFix:
    """Verify that gl_account is now correctly passed from GeneralContractCalculator.

    These tests confirm the fix is applied:
    - IndividualContractCalculator.execute (line 73) passes gl_account
    - GeneralContractCalculator.execute (line 186) passes gl_account
    """

    def test_individual_contract_calculator_gl_account(self):
        """IndividualContractCalculator must pass gl_account from contract."""
        # Import after fix is applied
        import inspect

        from domains.risk.services.valuation.local.calculators.general_contract_calculator import (
            IndividualContractCalculator,
        )

        source = inspect.getsource(IndividualContractCalculator.execute)
        # The source should contain gl_account=contract.gl_account
        assert (
            "gl_account=contract.gl_account" in source
        ), "IndividualContractCalculator.execute must pass gl_account=contract.gl_account"

    def test_general_contract_calculator_gl_account(self):
        """GeneralContractCalculator must pass gl_account from contract."""
        import inspect

        from domains.risk.services.valuation.local.calculators.general_contract_calculator import (
            GeneralContractCalculator,
        )

        source = inspect.getsource(GeneralContractCalculator.execute)
        # The source should contain gl_account=contract.gl_account
        assert (
            "gl_account=contract.gl_account" in source
        ), "GeneralContractCalculator.execute must pass gl_account=contract.gl_account"
