Feature: cashflow calculator

  Scenario Outline: Caclulating prepayments and final payments
    Given I have a contract with pricing uom "eur/MWh"
    Given the contract payment period is "month"
    Given the contract payment schedule contains prepayment at <prep_offset>, <prep_offset_unit>, <prep_pcnt>, <prep_value>
    Given the contract payment schedule contains final payment at <final_offset>, <final_offset_unit>, <final_pcnt>, <final_value>
    When the cashflow is calculated at valuation date <val_date> with value <value>
    Then the valuation result should have prepayment at date <expected_prep_date> for amount <expected_prep_value>
    Then the valuation result should have final payment at date <expected_final_date> for amount <expected_final_value>

    Examples: Payment options and expected resutls
      | name                   | val_date   | obs_date   | value | prep_offset | prep_offset_unit | prep_pcnt | prep_value | final_offset | final_offset_unit | final_pcnt | final_value | expected_prep_date | expected_prep_value | expected_final_date | expected_final_value |
      | final and prepayment 1 | 2025-02-15 | 2025-01-01 | 200.0 | -5          | calendar_day     | 20        | -          | 5            | business_day      | 80         | -           | 2025-01-27         | 40.0                | 2025-03-07          | 160.0                |
      | final and prepayment 2 | 2025-02-15 | 2025-01-01 | 200.0 | 6           | calendar_day     | 20        | -          | -5           | business_day      | 80         | -           | 2025-02-07         | 40.0                | 2025-02-21          | 160.0                |
      | final only 1           | 2025-02-15 | 2025-01-01 | 200.0 | -           | calendar_day     | -         | -          | 5            | business_day      | 100        | -           | -                  | -                   | 2025-03-07          | 200.0                |
      | final only 2           | 2025-02-15 | 2025-01-01 | 200.0 | -           | calendar_day     | -         | -          | -5           | business_day      | 100        | -           | -                  | -                   | 2025-02-21          | 200.0                |
# | prepayment only 1      | 2025-02-15 | 2025-01-01 | 200.0 | -5          | calendar_day     | 20        | -          | 5            | business_day      | 80         | -           | 2025-01-27         | 40.0                | 2025-03-07          | 160.0                |
# | prepayment only 2      | 2025-02-15 | 2025-01-01 | 200.0 | 6           | calendar_day     | 20        | -          | -5           | business_day      | -          | -           | 2025-01-27         | 40.0                | 2025-03-07          | 160.0                |
